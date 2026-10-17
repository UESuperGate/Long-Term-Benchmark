import { AccountProfile, RoomSummary, ScenarioInfo, TimelineEvent } from '../model/ElementModels';
import { MockMatrixService } from '../services/MockMatrixService';
import { createFunctionLevelAlignmentRows } from '../androidparity/FunctionLevelParity';

export class ElementBaseViewModel {
  private readonly service: MockMatrixService = new MockMatrixService();

  getScenarioInfo(): ScenarioInfo {
    return this.service.getScenarioInfo();
  }

  getAccountProfile(): AccountProfile {
    return this.service.getAccountProfile();
  }

  getRooms(): RoomSummary[] {
    return this.service.getRooms();
  }

  getTimelineEvents(): TimelineEvent[] {
    return this.service.getTimelineEvents();
  }

  getSecurityRows(): string[] {
    return this.service.getSecurityRows();
  }

  getFunctionLevelAlignmentRows(): string[] {
    return createFunctionLevelAlignmentRows(this.getScenarioInfo().scenarioId);
  }
}
