import router from '@ohos.router';
import { DemoRoomGateway, StartDMService, StartChatPresenter } from './ChatFeature';
import { RoomRouteParams, RoutePort, RouterChatNavigator } from './ChatRoutes';

export class HarmonyRoutePort implements RoutePort {
  async push(url: string): Promise<void> {
    await router.pushUrl({ url: url });
  }

  async replace(url: string, params: RoomRouteParams): Promise<void> {
    await router.replaceUrl({ url: url, params: params });
  }

  async returnToStart(): Promise<void> {
    if (Number(router.getLength()) > 1) {
      router.back();
    } else {
      await router.replaceUrl({ url: 'pages/Index' });
    }
  }
}

export const roomGateway: DemoRoomGateway = new DemoRoomGateway();
export const chatNavigator: RouterChatNavigator = new RouterChatNavigator(new HarmonyRoutePort());
export const startDMService: StartDMService = new StartDMService(roomGateway);
export const startChatPresenter: StartChatPresenter =
  new StartChatPresenter(roomGateway, startDMService, chatNavigator);
