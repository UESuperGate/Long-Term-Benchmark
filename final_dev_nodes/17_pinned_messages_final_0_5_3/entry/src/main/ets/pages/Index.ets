import common from '@ohos.app.ability.common';
import {
  PinnedMessage,
  PinnedMessagesListPresenter,
  PinnedMessagesListState,
  PinnedMessagesSession
} from '../features/PinnedMessagesFeature';

@Entry
@Component
struct Index {
  private presenter: PinnedMessagesListPresenter = PinnedMessagesSession.createPresenter();
  @State private screen: string = 'room_timeline';
  @State private listState: PinnedMessagesListState = PinnedMessagesListState.Idle;
  @State private pinnedMessages: PinnedMessage[] = [];
  @State private canPinUnpin: boolean = false;
  @State private errorMessage: string = '';
  @State private focusedEventId: string = '';
  @State private roomItems: PinnedMessage[] = [];
  @State private actionEventId: string = '';
  private unsubscribe: (() => void) | undefined = undefined;
  private roomScroller: Scroller = new Scroller();

  aboutToAppear(): void {
    this.unsubscribe = this.presenter.subscribe(() => this.syncPresenterState());
    this.presenter.startRoom(this.abilityContext());
    this.presenter.parent.load().then(() => {
      this.roomItems = this.presenter.parent.items.slice();
    }).catch(() => {
      this.errorMessage = 'Room timeline SDK service unavailable';
    });
  }

  aboutToDisappear(): void {
    this.unsubscribe?.();
    this.presenter.dispose();
  }

  build() {
    Column() {
      if (this.screen === 'pinned_messages') {
        this.PinnedMessagesList()
      } else {
        this.RoomTimeline()
      }
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  @Builder
  RoomTimeline() {
    Column() {
      Row() {
        Column({ space: 2 }) {
          Text('Design team')
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
          Text(this.focusedEventId.length > 0 ? `Focused ${this.focusedEventId}` : '12 members')
            .fontSize(13)
            .fontColor('#64748B')
            .id('focused_event_label')
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Text('Room')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')

      Row({ space: 12 }) {
        Text('Pinned')
          .fontSize(13)
          .fontWeight(FontWeight.Medium)
          .fontColor('#067A68')
        Text('Browse pinned messages')
          .layoutWeight(1)
        Button('Open')
          .onClick(() => this.openPinnedMessages())
          .id('open_pinned_messages')
      }
      .padding(14)
      .width('100%')
      .backgroundColor('#E9F8F4')
      .id('pinned_messages_banner')

      List({ scroller: this.roomScroller, space: 14 }) {
        ForEach(this.roomItems, (message: PinnedMessage) => {
          ListItem() {
            Column({ space: 8 }) {
              Text(message.sender).fontSize(13)
              Text(message.body).fontSize(16)
            }
            .width('100%')
            .padding(12)
            .backgroundColor(this.focusedEventId === message.eventId ? '#E9F8F4' : '#FFFFFF')
            .id(`room_event_${message.eventId}`)
          }
        }, (message: PinnedMessage) => message.eventId)
      }
      .padding(20)
      .layoutWeight(1)
      .width('100%')
      .id('room_timeline_events')
      if (this.errorMessage.length > 0) {
        Text(this.errorMessage).id('room_timeline_error')
      }
    }
  }

  @Builder
  PinnedMessagesList() {
    Column() {
      Row() {
        Button('Back')
          .onClick(() => {
            this.screen = 'room_timeline';
          })
          .id('pinned_messages_back')
        Text(this.listState === PinnedMessagesListState.Filled ? `${this.pinnedMessages.length} pinned messages` : 'Pinned messages')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .layoutWeight(1)
      }
      .padding(16)
      .width('100%')
      .backgroundColor('#FFFFFF')

      if (this.listState === PinnedMessagesListState.Loading) {
        Column({ space: 12 }) {
          LoadingProgress()
          Text('Loading pinned messages')
            .fontColor('#64748B')
        }
        .justifyContent(FlexAlign.Center)
        .layoutWeight(1)
        .width('100%')
        .id('pinned_messages_loading')
      } else if (this.listState === PinnedMessagesListState.Failed) {
        Column({ space: 14 }) {
          Text('Unable to load pinned messages')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
          Text(this.errorMessage)
            .fontColor('#B42318')
          Button('Retry')
            .onClick(() => this.retryLoad())
            .id('pinned_messages_retry')
        }
        .justifyContent(FlexAlign.Center)
        .padding(24)
        .layoutWeight(1)
        .width('100%')
        .id('pinned_messages_failed')
      } else if (this.listState === PinnedMessagesListState.Empty) {
        Column({ space: 10 }) {
          Text('No pinned messages')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
          Text('Pinned messages in this room will appear here.')
            .fontColor('#64748B')
        }
        .justifyContent(FlexAlign.Center)
        .layoutWeight(1)
        .width('100%')
        .id('pinned_messages_empty')
      } else {
        List({ space: 10 }) {
          ForEach(this.pinnedMessages, (message: PinnedMessage) => {
            ListItem() {
              Column({ space: 10 }) {
                Text(message.sender)
                  .fontSize(13)
                  .fontColor('#64748B')
                  .width('100%')
                Text(message.body)
                  .fontSize(16)
                  .lineHeight(22)
                  .width('100%')
                Button('Actions')
                  .id(`message_actions_${message.eventId}`)
                  .onClick(() => {
                    this.actionEventId = message.eventId;
                  })
                if (this.actionEventId === message.eventId) {
                  Row({ space: 10 }) {
                  Button('View in timeline')
                    .onClick(() => this.viewInTimeline(message.eventId))
                    .id(`view_in_timeline_${message.eventId}`)
                  if (this.canPinUnpin) {
                    Button('Unpin')
                      .backgroundColor('#B42318')
                      .onClick(() => this.unpin(message.eventId))
                      .id(`unpin_${message.eventId}`)
                  }
                  }
                  .width('100%')
                }
              }
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .width('100%')
              .backgroundColor('#FFFFFF')
              .borderRadius(8)
            }
          }, (message: PinnedMessage) => message.eventId)
        }
        .padding(14)
        .layoutWeight(1)
        .width('100%')
        .id('pinned_messages_filled')
      }

      if (this.errorMessage.length > 0 && this.listState !== PinnedMessagesListState.Failed) {
        Row({ space: 10 }) {
          Text(this.errorMessage)
            .fontColor('#B42318')
            .layoutWeight(1)
          Button('Retry')
            .enabled(this.presenter.retryEnabled && this.actionEventId.length > 0)
            .onClick(() => {
              this.unpin(this.actionEventId);
            })
            .id(`pinned_item_unpin_retry_${this.actionEventId}`)
          Button('Dismiss')
            .onClick(() => {
              this.presenter.dismissError();
              this.syncPresenterState();
            })
            .id('dismiss_unpin_error')
        }
        .padding(14)
        .width('100%')
        .backgroundColor('#FFF1F0')
        .id('unpin_error')
      }
    }
  }

  private abilityContext(): common.UIAbilityContext {
    return this.getUIContext().getHostContext() as common.UIAbilityContext;
  }

  private openPinnedMessages(): void {
    this.screen = 'pinned_messages';
    this.presenter.openPinnedMessages(this.abilityContext(), () => this.awaitLoadingFrame()).then(() => {
      this.syncPresenterState();
    });
    this.syncPresenterState();
  }

  private awaitLoadingFrame(): Promise<void> {
    return new Promise<void>((resolve: () => void) => {
      this.getUIContext().postFrameCallback({
        onFrame: () => {
        },
        onIdle: () => {
          resolve();
        }
      });
    });
  }

  private retryLoad(): void {
    this.presenter.retry(this.abilityContext()).then(() => this.syncPresenterState());
    this.syncPresenterState();
  }

  private viewInTimeline(eventId: string): void {
    this.presenter.viewInTimeline(eventId).then(() => {
      this.roomItems = this.presenter.parent.items.slice();
      this.focusedEventId = this.presenter.parent.focusedEventId;
      this.screen = 'room_timeline';
      this.getUIContext().postFrameCallback({
        onFrame: () => {},
        onIdle: () => this.roomScroller.scrollToIndex(this.presenter.parent.focusedIndex)
      });
    }).catch(() => {
      this.errorMessage = 'Unable to focus room timeline event';
    });
  }

  private unpin(eventId: string): void {
    this.presenter.unpin(this.abilityContext(), eventId).then(() => this.syncPresenterState());
  }

  private syncPresenterState(): void {
    this.listState = this.presenter.listState;
    this.pinnedMessages = this.presenter.pinnedMessages.slice();
    this.errorMessage = this.presenter.errorMessage;
    this.canPinUnpin = this.presenter.canPinUnpin;
  }
}
