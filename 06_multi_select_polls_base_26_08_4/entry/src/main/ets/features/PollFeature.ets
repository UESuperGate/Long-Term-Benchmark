export enum PollSubmissionState {
  Idle = 'idle',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export class PollAnswer {
  id: string;
  text: string;

  constructor(id: string, text: string) {
    this.id = id;
    this.text = text;
  }
}

export class PollDraft {
  question: string = '';
  answers: PollAnswer[] = [new PollAnswer('a', ''), new PollAnswer('b', '')];
  isDisclosed: boolean = true;
}

export class PollGateway {
  failNextRequest: boolean = false;
  lastCreatedQuestion: string = '';
  lastCreatedAnswers: string[] = [];
  lastResponseAnswerId: string = '';

  createPoll(question: string, answers: string[]): boolean {
    if (this.failNextRequest) {
      this.failNextRequest = false;
      return false;
    }
    this.lastCreatedQuestion = question;
    this.lastCreatedAnswers = answers.slice();
    return true;
  }

  sendPollResponse(answerId: string): boolean {
    if (this.failNextRequest) {
      this.failNextRequest = false;
      return false;
    }
    this.lastResponseAnswerId = answerId;
    return true;
  }
}

export class PollPresenter {
  readonly gateway: PollGateway;
  draft: PollDraft = new PollDraft();
  selectedAnswerId: string = '';
  submission: PollSubmissionState = PollSubmissionState.Idle;

  constructor(gateway: PollGateway) {
    this.gateway = gateway;
  }

  setQuestion(question: string): void {
    this.draft.question = question;
  }

  setAnswer(index: number, text: string): void {
    if (index >= 0 && index < this.draft.answers.length) {
      this.draft.answers[index].text = text;
    }
  }

  addAnswer(): void {
    const id = `answer-${this.draft.answers.length + 1}`;
    this.draft.answers.push(new PollAnswer(id, ''));
  }

  removeAnswer(index: number): void {
    if (this.draft.answers.length <= 2 || index < 0 || index >= this.draft.answers.length) {
      return;
    }
    this.draft.answers.splice(index, 1);
  }

  canSave(): boolean {
    const validAnswers = this.draft.answers.filter((answer: PollAnswer) => answer.text.trim().length > 0);
    return this.draft.question.trim().length > 0 && validAnswers.length >= 2;
  }

  save(): boolean {
    if (!this.canSave()) {
      return false;
    }
    this.submission = PollSubmissionState.Loading;
    const answers = this.draft.answers.map((answer: PollAnswer) => answer.text.trim());
    const succeeded = this.gateway.createPoll(this.draft.question.trim(), answers);
    this.submission = succeeded ? PollSubmissionState.Success : PollSubmissionState.Failure;
    return succeeded;
  }

  toggleAnswer(answerId: string): void {
    this.selectedAnswerId = this.selectedAnswerId === answerId ? '' : answerId;
  }

  isAnswerEnabled(ended: boolean): boolean {
    return !ended;
  }

  submitVote(): boolean {
    if (this.selectedAnswerId.length === 0) {
      return false;
    }
    this.submission = PollSubmissionState.Loading;
    const succeeded = this.gateway.sendPollResponse(this.selectedAnswerId);
    this.submission = succeeded ? PollSubmissionState.Success : PollSubmissionState.Failure;
    return succeeded;
  }
}
