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
  @State private childrenState: AsyncOperationState = AsyncOperationState.Idle;
  @State private paginationState: AsyncOperationState = AsyncOperationState.Idle;
  @State private statusText: string = 'Choose a Space';

  build() {
    Column() {
      this.Header()
      Scroll() {
        Column({ space: 12 }) {
          if (this.surface === SpaceSurface.Home) {
            Text('Your Spaces')
              .id('spaces_home')
              .fontSize(20)
              .fontWeight(FontWeight.Bold)
              .width('100%')
            ForEach(this.presenter.spaces, (space: SpaceRoom) => {
              Button(space.name)
                .id(`space_${space.roomId}`)
                .width('100%')
                .onClick(() => {
                  const loading = this.presenter.openSpace(space.roomId);
                  this.statusText = 'Loading Space children';
                  this.refresh();
                  loading.then(() => {
                    this.statusText = this.presenter.childrenState === AsyncOperationState.Success ?
                      'Space children loaded' : 'Unable to load Space children';
                    this.refresh();
                  });
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
                .id('spaces_home_button')
                .onClick(() => {
                  this.presenter.surface = SpaceSurface.Home;
                  this.refresh();
                })
              Text(`Space ${this.selectedSpaceId}`)
                .id('selected_space_id')
                .fontSize(20)
                .fontWeight(FontWeight.Bold)
                .layoutWeight(1)
            }
            .width('100%')
            if (this.childrenState === AsyncOperationState.Loading) {
              LoadingProgress().id('space_children_loading').width(24).height(24)
            }
            if (this.childrenState === AsyncOperationState.Failure) {
              Button('Retry loading')
                .id('space_children_retry')
                .onClick(() => {
                  const loading = this.presenter.openSpace(this.selectedSpaceId);
                  this.refresh();
                  loading.then(() => this.refresh());
                })
            }
            ForEach(this.children, (room: SpaceRoom) => {
              Row({ space: 8 }) {
                Text(`${room.name} ${room.membership}`)
                  .id(`space_child_${room.roomId}`)
                  .layoutWeight(1)
                if (room.membership.length === 0 && !room.isDirect) {
                  Button(this.joinLabel(room.roomId))
                    .id(`join_${room.roomId}`)
                    .onClick(() => {
                      const joining = this.presenter.joinChild(room.roomId);
                      this.statusText = 'Joining room';
                      this.refresh();
                      joining.then((joined: boolean) => {
                        this.statusText = joined ? 'Room joined' : 'Join failed';
                        this.refresh();
                      });
                    })
                }
              }
              .width('100%')
            })
            Row({ space: 8 }) {
              Button('Load more')
                .id('space_load_more')
                .enabled(this.hasMoreToLoad && this.childrenState === AsyncOperationState.Success &&
                  this.paginationState !== AsyncOperationState.Loading)
                .onClick(() => {
                  const loading = this.presenter.loadMore();
                  this.refresh();
                  loading.then(() => this.refresh());
                })
              Button('Fail next join')
                .id('fail_next_join')
                .onClick(() => {
                  this.presenter.gateway.failNextJoin = true;
                })
              Button('Clear failures')
                .id('clear_join_failures')
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
              .id('leave_space_surface')
              .fontSize(20)
              .fontWeight(FontWeight.Bold)
              .width('100%')
            ForEach(this.presenter.leaveCandidates(), (room: SpaceRoom) => {
              Row({ space: 8 }) {
                Checkbox({ name: room.roomId, group: 'leaveRooms' })
                  .id(`leave_room_${room.roomId}`)
                  .select(this.selectedLeaveRoomIds.includes(room.roomId))
                  .enabled(!room.isLastAdmin)
                  .onChange((selected: boolean) => {
                    const presenterSelected = this.presenter.selectedLeaveRoomIds.includes(room.roomId);
                    if (selected !== presenterSelected) {
                      this.presenter.toggleRoomSelection(room.roomId);
                      this.refresh();
                    }
                  })
                Text(room.isLastAdmin ? `${room.name} (last admin)` : room.name)
              }
              .width('100%')
            })
            Row({ space: 8 }) {
              Button('Select all')
                .id('select_all_leave_rooms')
                .onClick(() => {
                  this.presenter.selectAllRooms();
                  this.refresh();
                })
              Button('Deselect all')
                .id('deselect_all_leave_rooms')
                .onClick(() => {
                  this.presenter.deselectAllRooms();
                  this.refresh();
                })
            }
            Row({ space: 8 }) {
              Button('Fail next leave')
                .id('fail_next_leave')
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
                .id('close_leave_error')
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
    this.childrenState = this.presenter.childrenState;
    this.paginationState = this.presenter.paginationState;
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
