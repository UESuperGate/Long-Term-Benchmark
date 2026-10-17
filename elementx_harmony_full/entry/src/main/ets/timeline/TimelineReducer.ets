import {
  DomainError,
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../core/DomainResult';
import {
  GalleryContent,
  LocalSendState,
  LocationContent,
  MediaContent,
  PaginationDirection,
  PaginationState,
  PollContent,
  ReactionSummary,
  RedactedContent,
  SendQueueEntry,
  TimelineContent,
  TimelineContentKind,
  TimelineEvent,
  TimelineEventInput,
  TimelinePhase,
  TimelineRelationKind,
  TimelineSnapshot
} from '../matrix/api/TimelineModels';

function initialPagination(): PaginationState {
  return { isPaginating: false, hasMore: true, error: null };
}

function copyPagination(value: PaginationState): PaginationState {
  return { isPaginating: value.isPaginating, hasMore: value.hasMore, error: value.error };
}

function copyReaction(value: ReactionSummary): ReactionSummary {
  return {
    key: value.key,
    count: value.count,
    reactedByCurrentUser: value.reactedByCurrentUser,
    senderIds: value.senderIds.slice()
  };
}

function copyEvent(value: TimelineEvent): TimelineEvent {
  return {
    stableId: value.stableId,
    eventId: value.eventId,
    transactionId: value.transactionId,
    senderId: value.senderId,
    senderDisplayName: value.senderDisplayName,
    timestampMs: value.timestampMs,
    order: value.order,
    isOwn: value.isOwn,
    isRemote: value.isRemote,
    isEditable: value.isEditable,
    canBeRepliedTo: value.canBeRepliedTo,
    isEdited: value.isEdited,
    replyToEventId: value.replyToEventId,
    content: value.content,
    reactions: value.reactions.map((reaction: ReactionSummary) => copyReaction(reaction)),
    localSendState: value.localSendState,
    revision: value.revision
  };
}

function copyQueueEntry(value: SendQueueEntry): SendQueueEntry {
  return {
    transactionId: value.transactionId,
    eventId: value.eventId,
    stableId: value.stableId,
    state: value.state,
    progress: value.progress,
    error: value.error
  };
}

function relationIdentity(input: TimelineEventInput): string | null {
  if (input.eventId !== null) {
    return `event:${input.eventId}`;
  }
  if (input.transactionId !== null) {
    return `transaction:${input.transactionId}`;
  }
  return null;
}

export class TimelineReducer {
  private snapshot: TimelineSnapshot;
  private readonly pendingRelations: TimelineEventInput[] = [];
  private readonly processedRelations: string[] = [];

  constructor(roomId: string) {
    this.snapshot = {
      roomId: roomId,
      phase: TimelinePhase.Loading,
      items: [],
      backwardPagination: initialPagination(),
      forwardPagination: initialPagination(),
      sendQueue: [],
      error: null
    };
  }

  getSnapshot(): TimelineSnapshot {
    return {
      roomId: this.snapshot.roomId,
      phase: this.snapshot.phase,
      items: this.snapshot.items.map((item: TimelineEvent) => copyEvent(item)),
      backwardPagination: copyPagination(this.snapshot.backwardPagination),
      forwardPagination: copyPagination(this.snapshot.forwardPagination),
      sendQueue: this.snapshot.sendQueue.map((item: SendQueueEntry) => copyQueueEntry(item)),
      error: this.snapshot.error
    };
  }

  beginLoading(): TimelineSnapshot {
    this.snapshot.error = null;
    if (this.snapshot.items.length === 0) {
      this.snapshot.phase = TimelinePhase.Loading;
    }
    return this.getSnapshot();
  }

  merge(events: TimelineEventInput[]): DomainResult<TimelineSnapshot> {
    for (let index = 0; index < events.length; index += 1) {
      const validation = this.validate(events[index]);
      if (validation !== null) {
        return DomainResult.fail<TimelineSnapshot>(validation);
      }
    }
    events.forEach((event: TimelineEventInput) => this.applyInput(event));
    this.applyPendingRelations();
    this.sortItems();
    this.snapshot.phase = this.snapshot.items.length === 0 ? TimelinePhase.Empty : TimelinePhase.Ready;
    this.snapshot.error = null;
    return DomainResult.succeed<TimelineSnapshot>(this.getSnapshot());
  }

  beginPagination(direction: PaginationDirection): TimelineSnapshot {
    const state = this.pagination(direction);
    state.isPaginating = true;
    state.error = null;
    return this.getSnapshot();
  }

  finishPagination(direction: PaginationDirection, hasMore: boolean): TimelineSnapshot {
    const state = this.pagination(direction);
    state.isPaginating = false;
    state.hasMore = hasMore;
    state.error = null;
    return this.getSnapshot();
  }

  failPagination(direction: PaginationDirection, error: DomainError): TimelineSnapshot {
    const state = this.pagination(direction);
    state.isPaginating = false;
    state.error = error;
    return this.getSnapshot();
  }

  fail(error: DomainError, offline: boolean): TimelineSnapshot {
    this.snapshot.phase = offline ? TimelinePhase.Offline : TimelinePhase.Error;
    this.snapshot.error = error;
    return this.getSnapshot();
  }

  setOffline(isOffline: boolean): TimelineSnapshot {
    if (isOffline) {
      this.snapshot.phase = TimelinePhase.Offline;
    } else {
      this.snapshot.phase = this.snapshot.items.length === 0 ? TimelinePhase.Empty : TimelinePhase.Ready;
      this.snapshot.error = null;
    }
    return this.getSnapshot();
  }

  enqueueLocal(
    transactionId: string,
    senderId: string,
    timestampMs: number,
    content: TimelineContent,
    replyToEventId: string | null
  ): DomainResult<TimelineSnapshot> {
    if (transactionId.length === 0 || this.findByTransactionId(transactionId) >= 0) {
      return DomainResult.fail<TimelineSnapshot>(this.invalid('Transaction id must be non-empty and unique'));
    }
    const contentError = this.validateContent(content);
    if (contentError !== null) {
      return DomainResult.fail<TimelineSnapshot>(contentError);
    }
    const stableId = `transaction:${transactionId}`;
    this.snapshot.items.push({
      stableId: stableId,
      eventId: null,
      transactionId: transactionId,
      senderId: senderId,
      senderDisplayName: null,
      timestampMs: timestampMs,
      order: timestampMs,
      isOwn: true,
      isRemote: false,
      isEditable: true,
      canBeRepliedTo: false,
      isEdited: false,
      replyToEventId: replyToEventId,
      content: content,
      reactions: [],
      localSendState: LocalSendState.Queued,
      revision: 0
    });
    this.snapshot.sendQueue.push({
      transactionId: transactionId,
      eventId: null,
      stableId: stableId,
      state: LocalSendState.Queued,
      progress: null,
      error: null
    });
    this.sortItems();
    this.snapshot.phase = TimelinePhase.Ready;
    return DomainResult.succeed<TimelineSnapshot>(this.getSnapshot());
  }

  updateSendState(
    transactionId: string,
    state: LocalSendState,
    progress: number | null,
    error: DomainError | null
  ): DomainResult<TimelineSnapshot> {
    const queueIndex = this.snapshot.sendQueue.findIndex(
      (entry: SendQueueEntry) => entry.transactionId === transactionId
    );
    const eventIndex = this.findByTransactionId(transactionId);
    if (queueIndex < 0 || eventIndex < 0) {
      return DomainResult.fail<TimelineSnapshot>(this.invalid(`Unknown transaction ${transactionId}`));
    }
    if (progress !== null && (progress < 0 || progress > 1)) {
      return DomainResult.fail<TimelineSnapshot>(this.invalid('Upload progress must be between zero and one'));
    }
    this.snapshot.sendQueue[queueIndex].state = state;
    this.snapshot.sendQueue[queueIndex].progress = progress;
    this.snapshot.sendQueue[queueIndex].error = error;
    this.snapshot.items[eventIndex].localSendState = state;
    this.snapshot.items[eventIndex].revision += 1;
    if (state === LocalSendState.Cancelled) {
      this.snapshot.items.splice(eventIndex, 1);
    }
    return DomainResult.succeed<TimelineSnapshot>(this.getSnapshot());
  }

  acknowledgeSent(
    transactionId: string,
    eventId: string,
    timestampMs: number,
    order: number
  ): DomainResult<TimelineSnapshot> {
    if (eventId.length === 0) {
      return DomainResult.fail<TimelineSnapshot>(this.invalid('Acknowledged event id must not be empty'));
    }
    const eventIndex = this.findByTransactionId(transactionId);
    const queueIndex = this.snapshot.sendQueue.findIndex(
      (entry: SendQueueEntry) => entry.transactionId === transactionId
    );
    if (eventIndex < 0 || queueIndex < 0) {
      return DomainResult.fail<TimelineSnapshot>(this.invalid(`Unknown transaction ${transactionId}`));
    }
    const duplicateIndex = this.findByEventId(eventId);
    if (duplicateIndex >= 0 && duplicateIndex !== eventIndex) {
      this.mergeRemoteIntoLocal(eventIndex, duplicateIndex);
    }
    const updatedIndex = this.findByTransactionId(transactionId);
    const item = this.snapshot.items[updatedIndex];
    item.eventId = eventId;
    item.timestampMs = timestampMs;
    item.order = order;
    item.isRemote = true;
    item.canBeRepliedTo = true;
    item.localSendState = LocalSendState.Sent;
    item.revision += 1;
    this.snapshot.sendQueue[queueIndex].eventId = eventId;
    this.snapshot.sendQueue[queueIndex].state = LocalSendState.Sent;
    this.snapshot.sendQueue[queueIndex].error = null;
    this.sortItems();
    return DomainResult.succeed<TimelineSnapshot>(this.getSnapshot());
  }

  private applyInput(input: TimelineEventInput): void {
    if (input.relation !== null && input.relation.kind !== TimelineRelationKind.None &&
      input.relation.kind !== TimelineRelationKind.Reply) {
      this.applyRelationOrDefer(input);
      return;
    }
    let index = input.eventId === null ? -1 : this.findByEventId(input.eventId);
    if (index < 0 && input.transactionId !== null) {
      index = this.findByTransactionId(input.transactionId);
    }
    const replyTo = input.relation !== null && input.relation.kind === TimelineRelationKind.Reply ?
      input.relation.targetEventId : null;
    if (index >= 0) {
      const existing = this.snapshot.items[index];
      existing.eventId = input.eventId === null ? existing.eventId : input.eventId;
      existing.transactionId = input.transactionId === null ? existing.transactionId : input.transactionId;
      existing.senderDisplayName = input.senderDisplayName;
      existing.timestampMs = input.timestampMs;
      existing.order = input.order;
      existing.isRemote = input.eventId !== null;
      existing.canBeRepliedTo = input.eventId !== null;
      existing.replyToEventId = replyTo;
      existing.content = input.content;
      existing.localSendState = input.eventId !== null ? LocalSendState.Sent : existing.localSendState;
      existing.revision += 1;
      return;
    }
    this.snapshot.items.push({
      stableId: input.transactionId !== null ? `transaction:${input.transactionId}` : `event:${input.eventId}`,
      eventId: input.eventId,
      transactionId: input.transactionId,
      senderId: input.senderId,
      senderDisplayName: input.senderDisplayName,
      timestampMs: input.timestampMs,
      order: input.order,
      isOwn: input.isOwn,
      isRemote: input.eventId !== null,
      isEditable: input.isOwn && input.content.kind !== TimelineContentKind.Redacted,
      canBeRepliedTo: input.eventId !== null && input.content.kind !== TimelineContentKind.Redacted,
      isEdited: false,
      replyToEventId: replyTo,
      content: input.content,
      reactions: [],
      localSendState: input.eventId === null ? LocalSendState.Queued : null,
      revision: 0
    });
  }

  private applyRelationOrDefer(input: TimelineEventInput): void {
    const identity = relationIdentity(input);
    if (identity !== null && this.processedRelations.includes(identity)) {
      return;
    }
    const targetId = input.relation?.targetEventId;
    const targetIndex = targetId === undefined ? -1 : this.findByEventId(targetId);
    if (targetIndex < 0) {
      if (identity === null || !this.pendingRelations.some(
        (pending: TimelineEventInput) => relationIdentity(pending) === identity
      )) {
        this.pendingRelations.push(input);
      }
      return;
    }
    const target = this.snapshot.items[targetIndex];
    if (input.relation?.kind === TimelineRelationKind.Replacement) {
      if (target.senderId !== input.senderId) {
        return;
      }
      target.content = input.content;
      target.isEdited = true;
      target.revision += 1;
    } else if (input.relation?.kind === TimelineRelationKind.Reaction) {
      const key = input.relation.key;
      if (key === null || key.length === 0) {
        return;
      }
      let reaction = target.reactions.find((candidate: ReactionSummary) => candidate.key === key);
      if (reaction === undefined) {
        reaction = { key: key, count: 0, reactedByCurrentUser: false, senderIds: [] };
        target.reactions.push(reaction);
        target.reactions.sort((left: ReactionSummary, right: ReactionSummary) => left.key.localeCompare(right.key));
      }
      if (!reaction.senderIds.includes(input.senderId)) {
        reaction.senderIds.push(input.senderId);
        reaction.senderIds.sort();
        reaction.count = reaction.senderIds.length;
        reaction.reactedByCurrentUser = reaction.reactedByCurrentUser || input.isOwn;
        target.revision += 1;
      }
    } else if (input.relation?.kind === TimelineRelationKind.Redaction) {
      const redacted: RedactedContent = { kind: TimelineContentKind.Redacted, reason: null };
      target.content = redacted;
      target.isEditable = false;
      target.canBeRepliedTo = false;
      target.isEdited = false;
      target.revision += 1;
    }
    if (identity !== null) {
      this.processedRelations.push(identity);
    }
  }

  private applyPendingRelations(): void {
    let index = 0;
    while (index < this.pendingRelations.length) {
      const pending = this.pendingRelations[index];
      const targetId = pending.relation?.targetEventId;
      if (targetId !== undefined && this.findByEventId(targetId) >= 0) {
        this.pendingRelations.splice(index, 1);
        this.applyRelationOrDefer(pending);
      } else {
        index += 1;
      }
    }
  }

  private validate(input: TimelineEventInput): DomainFailure | null {
    if ((input.eventId === null || input.eventId.length === 0) &&
      (input.transactionId === null || input.transactionId.length === 0)) {
      return this.invalid('Timeline event needs an event id or transaction id');
    }
    if (input.senderId.length === 0 || input.timestampMs < 0) {
      return this.invalid('Timeline event sender and timestamp are invalid');
    }
    if (input.relation !== null && input.relation.kind !== TimelineRelationKind.None &&
      input.relation.targetEventId.length === 0) {
      return this.invalid('Timeline relation target must not be empty');
    }
    return this.validateContent(input.content);
  }

  private validateContent(content: TimelineContent): DomainFailure | null {
    if (content.kind === TimelineContentKind.Gallery) {
      const gallery = content as GalleryContent;
      if (gallery.items.length === 0) {
        return this.invalid('Gallery events require at least one media item');
      }
    }
    if (content.kind === TimelineContentKind.Image || content.kind === TimelineContentKind.Video ||
      content.kind === TimelineContentKind.Audio || content.kind === TimelineContentKind.File) {
      const media = content as MediaContent;
      if (media.media.sourceUrl.length === 0 || media.media.fileName.length === 0) {
        return this.invalid('Media events require a source and filename');
      }
    }
    if (content.kind === TimelineContentKind.Location) {
      const location = content as LocationContent;
      if (!location.geoUri.startsWith('geo:')) {
        return this.invalid('Location event requires an RFC 5870 geo URI');
      }
    }
    if (content.kind === TimelineContentKind.Poll) {
      const poll = content as PollContent;
      if (poll.question.length === 0 || poll.answers.length < 2 || poll.maxSelections < 1) {
        return this.invalid('Poll event requires a question, choices, and a positive selection limit');
      }
    }
    return null;
  }

  private mergeRemoteIntoLocal(localIndex: number, remoteIndex: number): void {
    const local = this.snapshot.items[localIndex];
    const remote = this.snapshot.items[remoteIndex];
    local.content = remote.content;
    local.reactions = remote.reactions;
    local.senderDisplayName = remote.senderDisplayName;
    this.snapshot.items.splice(remoteIndex, 1);
  }

  private findByEventId(eventId: string): number {
    return this.snapshot.items.findIndex((item: TimelineEvent) => item.eventId === eventId);
  }

  private findByTransactionId(transactionId: string): number {
    return this.snapshot.items.findIndex((item: TimelineEvent) => item.transactionId === transactionId);
  }

  private pagination(direction: PaginationDirection): PaginationState {
    return direction === PaginationDirection.Backwards ?
      this.snapshot.backwardPagination : this.snapshot.forwardPagination;
  }

  private sortItems(): void {
    this.snapshot.items.sort((left: TimelineEvent, right: TimelineEvent) => {
      const byTimestamp = left.timestampMs - right.timestampMs;
      if (byTimestamp !== 0) {
        return byTimestamp;
      }
      const byOrder = left.order - right.order;
      return byOrder !== 0 ? byOrder : left.stableId.localeCompare(right.stableId);
    });
  }

  private invalid(message: string): DomainFailure {
    return new DomainFailure(DomainErrorCode.InvalidInput, message, false);
  }
}
