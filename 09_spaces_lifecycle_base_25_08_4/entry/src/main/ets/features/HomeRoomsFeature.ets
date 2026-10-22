export class HomeRoom {
  roomId: string;
  name: string;

  constructor(roomId: string, name: string) {
    this.roomId = roomId;
    this.name = name;
  }
}

export enum HomeSurface {
  Chats = 'chats',
  Spaces = 'spaces'
}

export class HomeRoomsPresenter {
  rooms: HomeRoom[] = [
    new HomeRoom('!design', 'Design'),
    new HomeRoom('!engineering', 'Engineering')
  ];
  selectedRoomId: string = '';
  surface: HomeSurface = HomeSurface.Chats;

  openRoom(roomId: string): void {
    this.selectedRoomId = roomId;
  }

  openChats(): void {
    this.surface = HomeSurface.Chats;
  }

  openSpaces(): void {
    this.surface = HomeSurface.Spaces;
  }
}
