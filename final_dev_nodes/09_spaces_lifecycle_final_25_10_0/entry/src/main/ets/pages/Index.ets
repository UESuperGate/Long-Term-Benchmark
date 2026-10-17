import { AsyncOperationState, RoomAction, SpaceRoom, SpacesGateway, SpacesPresenter, SpaceSurface } from '../features/SpacesFeature';

@Entry
@Component
struct Index {
  private presenter: SpacesPresenter = new SpacesPresenter(new SpacesGateway());
  @State private surface: SpaceSurface = SpaceSurface.Home;
  @State private selectedSpaceId: string = '';
  @State private children: SpaceRoom[] = [];
  @State private joinActions: RoomAction[] = [];
  @State private selectedLeaveRoomIds: string[] = [];
  @State private leaveState: AsyncOperationState = AsyncOperationState.Idle;
  @State private hasMoreToLoad: boolean = true;
  @State private statusText: string = 'Choose a Space';

  build() {
    Column() {
      this.Header()
      Scroll() {
        Column({ space: 12 }) {
          if (this.surface === SpaceSurface.Home) {
            Text('Your Spaces')
              .fontSize(20)
              .fontWeight(FontWeight.Bold)
              .width('100%')
            ForEach(this.presenter.spaces, (space: SpaceRoom) => {
              Button(space.name)
                .id(`space_${space.roomId}`)
                .width('100%')
                .onClick(() => {
                  this.presenter.openSpace(space.roomId);
                  this.statusText = 'Space children loaded';
                  this.refresh();
                })
            })
            Text('Invitations')
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .width('100%')
            ForEach(this.presenter.invites, (invite: SpaceRoom) => {
              Button(`Accept ${invite.name}`)
                .id(`accept_space_${invite.roomId}`)
                .width('100%')
                .onClick(() => {
                  this.presenter.acceptInvite(invite.roomId);
                  this.statusText = 'Space invitation accepted';
                  this.refresh();
                })
            })
          } else if (this.surface === SpaceSurface.Space) {
            Row() {
              Button('Home')
                .onClick(() => {
                  this.presenter.surface = SpaceSurface.Home;
                  this.refresh();
                })
              Text(`Space ${this.selectedSpaceId}`)
                .fontSize(20)
                .fontWeight(FontWeight.Bold)
                .layoutWeight(1)
            }
            .width('100%')
            ForEach(this.children, (room: SpaceRoom) => {
              Row({ space: 8 }) {
                Text(`${room.name} ${room.membership}`)
                  .layoutWeight(1)
                if (room.membership.length === 0 && !room.isDirect) {
                  Button(this.joinLabel(room.roomId))
                    .id(`join_${room.roomId}`)
                    .onClick(() => {
                      this.statusText = this.presenter.joinChild(room.roomId) ? 'Room joined' : 'Join failed';
                      this.refresh();
                    })
                }
              }
              .width('100%')
            })
            Row({ space: 8 }) {
              Button('Load more')
                .id('space_load_more')
                .enabled(this.hasMoreToLoad)
                .onClick(() => {
                  this.presenter.loadMore();
                  this.refresh();
                })
              Button('Fail next join')
                .onClick(() => {
                  this.presenter.gateway.failNextJoin = true;
                })
              Button('Clear failures')
                .onClick(() => {
                  this.presenter.clearJoinFailures();
                  this.refresh();
                })
            }
            Button('Leave Space')
              .id('open_leave_space')
              .width('100%')
              .onClick(() => {
                this.presenter.openLeaveSpace();
                this.refresh();
              })
          } else {
            Text('Leave Space')
              .fontSize(20)
              .fontWeight(FontWeight.Bold)
              .width('100%')
            ForEach(this.presenter.leaveCandidates(), (room: SpaceRoom) => {
              Row({ space: 8 }) {
                Checkbox({ name: room.roomId, group: 'leaveRooms' })
                  .select(this.selectedLeaveRoomIds.includes(room.roomId))
                  .enabled(!room.isLastAdmin)
                  .onChange(() => {
                    this.presenter.toggleRoomSelection(room.roomId);
                    this.refresh();
                  })
                Text(room.isLastAdmin ? `${room.name} (last admin)` : room.name)
              }
              .width('100%')
            })
            Row({ space: 8 }) {
              Button('Select all')
                .onClick(() => {
                  this.presenter.selectAllRooms();
                  this.refresh();
                })
              Button('Deselect all')
                .onClick(() => {
                  this.presenter.deselectAllRooms();
                  this.refresh();
                })
            }
            Row({ space: 8 }) {
              Button('Fail next leave')
                .onClick(() => {
                  this.presenter.gateway.failNextLeave = true;
                })
              Button(this.leaveState === AsyncOperationState.Failure ? 'Retry leave' : 'Confirm leave')
                .id('confirm_leave_space')
                .onClick(() => {
                  this.statusText = this.presenter.leaveSpace() ? 'Space left' : 'Leave failed; selection kept';
                  this.refresh();
                })
              Button('Close error')
                .enabled(this.leaveState === AsyncOperationState.Failure)
                .onClick(() => {
                  this.presenter.closeLeaveError();
                  this.refresh();
                })
            }
          }
          Text(this.statusText)
            .id('spaces_status')
            .fontColor('#475569')
            .width('100%')
        }
        .padding(20)
        .width('100%')
      }
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private joinLabel(roomId: string): string {
    const action = this.presenter.actionFor(roomId);
    if (action === undefined || action.state === AsyncOperationState.Idle) {
      return 'Join';
    }
    return action.state === AsyncOperationState.Failure ? 'Retry' : action.state;
  }

  private refresh(): void {
    this.surface = this.presenter.surface;
    this.selectedSpaceId = this.presenter.selectedSpaceId;
    this.children = this.presenter.children.slice();
    this.joinActions = this.presenter.joinActions.slice();
    this.selectedLeaveRoomIds = this.presenter.selectedLeaveRoomIds.slice();
    this.leaveState = this.presenter.leaveState;
    this.hasMoreToLoad = this.presenter.hasMoreToLoad;
  }

  @Builder
  Header() {
    Column({ space: 4 }) {
      Text('Element X Spaces')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
      Text('Android v25.10.0 behavior: browse, join and leave Spaces')
        .fontSize(13)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(20)
    .width('100%')
    .backgroundColor('#FFFFFF')
  }
}
