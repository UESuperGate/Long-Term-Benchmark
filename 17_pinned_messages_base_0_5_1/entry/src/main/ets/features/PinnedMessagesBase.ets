export class PinnedBannerMessage {
  eventId: string;
  body: string;

  constructor(eventId: string, body: string) {
    this.eventId = eventId;
    this.body = body;
  }
}

export class PinnedMessagesBannerPresenter {
  pinnedMessages: PinnedBannerMessage[] = [
    new PinnedBannerMessage('$welcome', 'Welcome to the room'),
    new PinnedBannerMessage('$rules', 'Please read the room rules')
  ];
  currentIndex: number = 1;

  current(): PinnedBannerMessage | null {
    if (this.pinnedMessages.length === 0) {
      return null;
    }
    return this.pinnedMessages[this.currentIndex];
  }

  moveToNext(): void {
    if (this.pinnedMessages.length === 0) {
      return;
    }
    this.currentIndex = (this.currentIndex - 1 + this.pinnedMessages.length) % this.pinnedMessages.length;
  }
}
