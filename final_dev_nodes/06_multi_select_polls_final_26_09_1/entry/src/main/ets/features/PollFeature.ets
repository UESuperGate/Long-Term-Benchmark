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
  maxSelections: number = 1;
}

export class PollGateway {
  failNextRequest: boolean = false;
  lastCreatedQuestion: string = '';
  lastCreatedAnswers: string[] = [];
  lastCreatedMaxSelections: number = 1;
  lastResponseAnswerIds: string[] = [];

  createPoll(question: string, answers: string[], maxSelections: number): boolean {
    if (this.failNextRequest) {
      this.failNextRequest = false;
      return false;
    }
    this.lastCreatedQuestion = question;
    this.lastCreatedAnswers = answers.slice();
    this.lastCreatedMaxSelections = maxSelections;
    return true;
  }

  sendPollResponse(answerIds: string[]): boolean {
    if (this.failNextRequest) {
      this.failNextRequest = false;
      return false;
    }
    this.lastResponseAnswerIds = answerIds.slice();
    return true;
  }
}

export class PollPresenter {
  readonly gateway: PollGateway;
  draft: PollDraft = new PollDraft();
  selectedAnswerIds: string[] = [];
  submission: PollSubmissionState = PollSubmissionState.Idle;

  constructor(gateway: PollGateway) {
    this.gateway = gateway;
  }

  get maxAllowedSelections(): number {
    return this.draft.answers.length;
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
    const removedId = this.draft.answers[index].id;
    this.draft.answers.splice(index, 1);
    this.draft.maxSelections = this.clampMaxSelections(this.draft.maxSelections);
    this.selectedAnswerIds = this.selectedAnswerIds.filter((answerId: string) => answerId !== removedId);
  }

  setMaxSelections(maxSelections: number): void {
    this.draft.maxSelections = this.clampMaxSelections(maxSelections);
    if (this.selectedAnswerIds.length > this.draft.maxSelections) {
      this.selectedAnswerIds = this.selectedAnswerIds.slice(0, this.draft.maxSelections);
    }
  }

  loadExisting(question: string, answers: PollAnswer[], isDisclosed: boolean, maxSelections: number): void {
    this.draft.question = question;
    this.draft.answers = answers.map((answer: PollAnswer) => new PollAnswer(answer.id, answer.text));
    this.draft.isDisclosed = isDisclosed;
    this.draft.maxSelections = this.clampMaxSelections(maxSelections);
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
    const succeeded = this.gateway.createPoll(
      this.draft.question.trim(),
      answers,
      this.draft.maxSelections
    );
    this.submission = succeeded ? PollSubmissionState.Success : PollSubmissionState.Failure;
    return succeeded;
  }

  toggleAnswer(answerId: string): void {
    if (this.selectedAnswerIds.includes(answerId)) {
      this.selectedAnswerIds = this.selectedAnswerIds.filter((selected: string) => selected !== answerId);
      return;
    }
    if (this.selectedAnswerIds.length < this.draft.maxSelections) {
      this.selectedAnswerIds = this.selectedAnswerIds.concat(answerId);
    }
  }

  isAnswerEnabled(answerId: string, ended: boolean): boolean {
    if (ended) {
      return false;
    }
    const limitReached = this.selectedAnswerIds.length >= this.draft.maxSelections;
    return !limitReached || this.selectedAnswerIds.includes(answerId);
  }

  submitVote(): boolean {
    if (this.selectedAnswerIds.length === 0) {
      return false;
    }
    this.submission = PollSubmissionState.Loading;
    const succeeded = this.gateway.sendPollResponse(this.selectedAnswerIds);
    this.submission = succeeded ? PollSubmissionState.Success : PollSubmissionState.Failure;
    return succeeded;
  }

  private clampMaxSelections(value: number): number {
    return Math.max(1, Math.min(value, this.maxAllowedSelections));
  }
}
