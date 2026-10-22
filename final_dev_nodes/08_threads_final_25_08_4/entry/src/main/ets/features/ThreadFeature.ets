export enum ThreadSurface {
  Room = 'room',
  Thread = 'thread',
  AttachmentPreview = 'attachment_preview',
  LocationPicker = 'location_picker',
  PollComposer = 'poll_composer'
}

export enum ThreadSendState {
  Idle = 'idle',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export enum ThreadFocusState {
  Idle = 'idle',
  Success = 'success',
  Failure = 'failure'
}

export class ThreadGateway {
  getRoomTimeline(): string[] {
    return ['$root', '$reply', '$other'];
  }

  getThreadTimeline(threadRootId: string): string[] {
    return this.getRoomTimeline().filter((eventId: string) => eventId === threadRootId || eventId === '$reply');
  }

  failNextSend: boolean = false;
  lastEffect: string = '';
  lastBody: string = '';
  lastThreadRootId: string = '';
  lastReplyTargetId: string = '';
  attempts: number = 0;

  sendMessage(body: string, threadRootId: string, replyTargetId: string): boolean {
    this.attempts += 1;
    if (this.failNextSend) {
      this.failNextSend = false;
      return false;
    }
    this.lastEffect = replyTargetId.length > 0 ? 'reply_message' : 'send_message';
    this.lastBody = body;
    this.lastThreadRootId = threadRootId;
    this.lastReplyTargetId = replyTargetId;
    return true;
  }

  sendAttachment(attachmentId: string, caption: string, threadRootId: string): boolean {
    this.attempts += 1;
    if (this.failNextSend) {
      this.failNextSend = false;
      return false;
    }
    this.lastEffect = 'send_attachment';
    this.lastBody = `${attachmentId}:${caption}`;
    this.lastThreadRootId = threadRootId;
    return true;
  }
}

export class ThreadPresenter {
  readonly gateway: ThreadGateway;
  mainRoomEvents: string[];
  threadEvents: string[] = [];
  surface: ThreadSurface = ThreadSurface.Room;
  threadRootId: string = '';
  focusedEventId: string | null = '';
  focusState: ThreadFocusState = ThreadFocusState.Idle;
  composerText: string = '';
  replyTargetId: string = '';
  sendState: ThreadSendState = ThreadSendState.Idle;

  constructor(gateway: ThreadGateway) {
    this.gateway = gateway;
    this.mainRoomEvents = gateway.getRoomTimeline().slice();
  }

  openThread(threadRootId: string): void {
    this.threadRootId = threadRootId;
    this.threadEvents = this.gateway.getThreadTimeline(threadRootId).slice();
    this.surface = ThreadSurface.Thread;
    this.focusedEventId = '';
    this.focusState = ThreadFocusState.Idle;
  }

  focusEvent(eventId: string): boolean {
    if (!this.threadEvents.includes(eventId)) {
      this.focusedEventId = null;
      this.focusState = ThreadFocusState.Failure;
      return false;
    }
    this.focusedEventId = eventId;
    this.focusState = ThreadFocusState.Success;
    return true;
  }

  setComposerText(value: string): void {
    this.composerText = value;
  }

  setReplyTarget(eventId: string): void {
    // Reply identity belongs to the timeline, not its currently visible window.
    if (this.threadRootId.length > 0 && eventId.length > 0) {
      this.replyTargetId = eventId;
    }
  }

  cancelReply(): void {
    this.replyTargetId = '';
  }

  sendMessage(): boolean {
    const body = this.composerText.trim();
    if (this.surface !== ThreadSurface.Thread || this.threadRootId.length === 0 || body.length === 0) {
      return false;
    }
    this.sendState = ThreadSendState.Loading;
    const succeeded = this.gateway.sendMessage(body, this.threadRootId, this.replyTargetId);
    this.sendState = succeeded ? ThreadSendState.Success : ThreadSendState.Failure;
    if (succeeded) {
      this.threadEvents = this.threadEvents.concat(body);
      this.composerText = '';
      this.replyTargetId = '';
    }
    return succeeded;
  }

  retrySend(): boolean {
    return this.sendMessage();
  }

  sendAttachment(attachmentId: string, caption: string): boolean {
    if (this.surface !== ThreadSurface.Thread || this.threadRootId.length === 0) {
      return false;
    }
    this.sendState = ThreadSendState.Loading;
    const succeeded = this.gateway.sendAttachment(attachmentId, caption, this.threadRootId);
    this.sendState = succeeded ? ThreadSendState.Success : ThreadSendState.Failure;
    return succeeded;
  }

  openAttachmentPreview(): void {
    this.openNestedSurface(ThreadSurface.AttachmentPreview);
  }

  openNestedSurface(surface: ThreadSurface): void {
    if (this.surface !== ThreadSurface.Thread || this.threadRootId.length === 0) {
      return;
    }
    if (surface === ThreadSurface.AttachmentPreview || surface === ThreadSurface.LocationPicker ||
      surface === ThreadSurface.PollComposer) {
      this.surface = surface;
    }
  }

  returnToThread(): void {
    if (this.threadRootId.length > 0) {
      this.surface = ThreadSurface.Thread;
    }
  }

  navigateBack(): void {
    this.surface = ThreadSurface.Room;
    this.threadRootId = '';
    this.focusedEventId = '';
    this.replyTargetId = '';
    this.composerText = '';
  }
}
