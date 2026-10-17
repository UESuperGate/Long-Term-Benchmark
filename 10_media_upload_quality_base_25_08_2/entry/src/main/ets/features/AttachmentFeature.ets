export enum AttachmentSendState {
  Idle = 'idle',
  Sending = 'sending',
  Done = 'done',
  Failure = 'failure'
}

export class AttachmentGateway {
  failNextSend: boolean = false;
  lastCaption: string = '';

  send(caption: string): boolean {
    if (this.failNextSend) {
      this.failNextSend = false;
      return false;
    }
    this.lastCaption = caption;
    return true;
  }
}

export class AttachmentPresenter {
  readonly gateway: AttachmentGateway;
  caption: string = '';
  sendState: AttachmentSendState = AttachmentSendState.Idle;

  constructor(gateway: AttachmentGateway) {
    this.gateway = gateway;
  }

  setCaption(caption: string): void {
    this.caption = caption;
  }

  send(): boolean {
    this.sendState = AttachmentSendState.Sending;
    const succeeded = this.gateway.send(this.caption);
    this.sendState = succeeded ? AttachmentSendState.Done : AttachmentSendState.Failure;
    return succeeded;
  }
}
