export class HomeRoom {
  roomId: string;
  name: string;

  constructor(roomId: string, name: string) {
    this.roomId = roomId;
    this.name = name;
  }
}

export class HomeRoomsPresenter {
  rooms: HomeRoom[] = [
    new HomeRoom('!design', 'Design'),
    new HomeRoom('!engineering', 'Engineering')
  ];
  selectedRoomId: string = '';

  openRoom(roomId: string): void {
    this.selectedRoomId = roomId;
  }
}
