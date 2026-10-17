export enum RoomSendState {
  Idle = 'idle',
  Success = 'success',
  Failure = 'failure'
}

export class RoomTimelineGateway {
  failNextRequest: boolean = false;
  lastBody: string = '';

  sendMessage(body: string): boolean {
    if (this.failNextRequest) {
      this.failNextRequest = false;
      return false;
    }
    this.lastBody = body;
    return true;
  }
}

export class RoomTimelinePresenter {
  readonly gateway: RoomTimelineGateway;
  events: string[] = ['$welcome', '$roadmap'];
  composerText: string = '';
  sendState: RoomSendState = RoomSendState.Idle;

  constructor(gateway: RoomTimelineGateway) {
    this.gateway = gateway;
  }

  setComposerText(value: string): void {
    this.composerText = value;
  }

  sendMessage(): boolean {
    const body = this.composerText.trim();
    if (body.length === 0) {
      return false;
    }
    const succeeded = this.gateway.sendMessage(body);
    this.sendState = succeeded ? RoomSendState.Success : RoomSendState.Failure;
    if (succeeded) {
      this.events = this.events.concat(body);
      this.composerText = '';
    }
    return succeeded;
  }
}
