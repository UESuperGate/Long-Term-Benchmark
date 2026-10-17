import common from '@ohos.app.ability.common';
import picker from '@ohos.file.picker';
import {
  NotificationChannelGateway,
  NotificationSettingsPresenter,
  NotificationSoundCopier,
  NotificationSoundKind,
  NotificationSoundSelection,
  NotificationSoundStore,
  SoundSlot
} from '../features/NotificationSoundFeature';

@Entry
@Component
struct Index {
  private presenter: NotificationSettingsPresenter = new NotificationSettingsPresenter(
    new NotificationSoundStore(),
    new NotificationSoundCopier(),
    new NotificationChannelGateway()
  );
  @State private messageSound: NotificationSoundSelection = NotificationSoundSelection.preset(NotificationSoundKind.SystemDefault);
  @State private callRingtone: NotificationSoundSelection = NotificationSoundSelection.preset(NotificationSoundKind.SystemDefault);
  @State private showMessageDialog: boolean = false;
  @State private showCallDialog: boolean = false;
  @State private messageError: string = '';
  @State private callError: string = '';
  @State private statusText: string = 'Loading notification sounds';

  build() {
    Stack({ alignContent: Alignment.Bottom }) {
      Column() {
        Column({ space: 4 }) {
          Text('Notifications')
            .fontSize(24)
            .fontWeight(FontWeight.Bold)
          Text('Message sounds and call ringtones')
            .fontSize(13)
            .fontColor('#64748B')
        }
        .alignItems(HorizontalAlign.Start)
        .padding(20)
        .width('100%')
        .backgroundColor('#FFFFFF')

        Scroll() {
          Column({ space: 12 }) {
            this.SoundRow('Message sound', this.messageSound.displayName, () => {
              this.presenter.showDialog(SoundSlot.Message);
              this.syncPresenterState();
            }, 'message_sound_row')
            this.SoundRow('Call ringtone', this.callRingtone.displayName, () => {
              this.presenter.showDialog(SoundSlot.Call);
              this.syncPresenterState();
            }, 'call_ringtone_row')

            if (this.messageError.length > 0) {
              this.ErrorRow(this.messageError, () => {
                this.presenter.dismissCopyError(SoundSlot.Message);
                this.syncPresenterState();
              }, 'message_sound_error')
            }
            if (this.callError.length > 0) {
              this.ErrorRow(this.callError, () => {
                this.presenter.dismissCopyError(SoundSlot.Call);
                this.syncPresenterState();
              }, 'call_ringtone_error')
            }

            Text(this.statusText)
              .fontSize(13)
              .fontColor('#64748B')
              .padding(8)
              .width('100%')
              .id('sound_update_status')
          }
          .padding(16)
          .width('100%')
        }
        .layoutWeight(1)
      }
      .height('100%')
      .width('100%')
      .backgroundColor('#F4F6F8')
      .onAppear(() => {
        this.presenter.load(this.abilityContext()).then(() => {
          this.statusText = 'Sound preferences restored';
          this.syncPresenterState();
        }).catch((error: Error) => {
          this.statusText = `Unable to restore sounds: ${error.message}`;
        });
      })

      if (this.showMessageDialog) {
        this.SoundDialog('Message sound', SoundSlot.Message)
      }
      if (this.showCallDialog) {
        this.SoundDialog('Call ringtone', SoundSlot.Call)
      }
    }
    .height('100%')
    .width('100%')
  }

  @Builder
  SoundRow(label: string, value: string, onClick: () => void, rowId: string) {
    Button() {
      Row() {
        Column({ space: 3 }) {
          Text(label)
            .fontSize(16)
            .fontColor('#0F172A')
          Text(value)
            .fontSize(13)
            .fontColor('#64748B')
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)
        Text('Change')
          .fontSize(14)
          .fontColor('#067A68')
      }
      .width('100%')
    }
    .height(70)
    .padding({ left: 16, right: 16 })
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
    .onClick(onClick)
    .id(rowId)
  }

  @Builder
  ErrorRow(message: string, onDismiss: () => void, rowId: string) {
    Row({ space: 10 }) {
      Text(message)
        .fontSize(13)
        .fontColor('#B42318')
        .layoutWeight(1)
      Button('Dismiss')
        .onClick(onDismiss)
        .id(`${rowId}_dismiss`)
    }
    .padding(14)
    .width('100%')
    .backgroundColor('#FFF1F0')
    .borderRadius(8)
    .id(rowId)
  }

  @Builder
  SoundDialog(title: string, slot: SoundSlot) {
    Column() {
      Blank()
        .layoutWeight(1)
      Column({ space: 10 }) {
        Row() {
          Text(title)
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
            .layoutWeight(1)
          Button('Close')
            .onClick(() => {
              this.presenter.dismissDialog(slot);
              this.syncPresenterState();
            })
            .id(`${slot}_sound_dialog_close`)
        }
        this.PresetButton('System default', slot, NotificationSoundKind.SystemDefault)
        this.PresetButton('Element default', slot, NotificationSoundKind.ElementDefault)
        this.PresetButton('Element fade', slot, NotificationSoundKind.ElementFade)
        this.PresetButton('Silent', slot, NotificationSoundKind.Silent)
        Button('Choose audio file')
          .width('100%')
          .onClick(() => this.launchAudioPicker(slot))
          .id(`${slot}_sound_picker`)
      }
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      .borderRadius({ topLeft: 8, topRight: 8 })
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#66000000')
    .id(`${slot}_sound_dialog`)
  }

  @Builder
  PresetButton(label: string, slot: SoundSlot, kind: NotificationSoundKind) {
    Button(label)
      .width('100%')
      .backgroundColor('#EEF2F7')
      .fontColor('#0F172A')
      .onClick(() => this.selectPreset(slot, kind))
      .id(`${slot}_preset_${kind}`)
  }

  private abilityContext(): common.UIAbilityContext {
    return this.getUIContext().getHostContext() as common.UIAbilityContext;
  }

  private selectPreset(slot: SoundSlot, kind: NotificationSoundKind): void {
    this.statusText = 'Updating notification channel';
    this.presenter.selectPreset(this.abilityContext(), slot, kind).then((succeeded: boolean) => {
      this.statusText = succeeded ? 'Sound and notification channel updated' : 'The previous sound was kept';
      this.syncPresenterState();
    });
    this.syncPresenterState();
  }

  private launchAudioPicker(slot: SoundSlot): void {
    this.presenter.launchSystemPicker(slot);
    this.syncPresenterState();
    this.statusText = 'Choose an audio file';
    const audioPicker = new picker.AudioViewPicker(this.abilityContext());
    audioPicker.select().then((uris: string[]) => {
      if (uris.length === 0) {
        this.statusText = 'Sound selection cancelled';
        return;
      }
      this.statusText = 'Copying sound into app storage';
      this.presenter.setCustomSound(this.abilityContext(), slot, uris[0]).then((succeeded: boolean) => {
        this.statusText = succeeded ? 'Custom sound and notification channel updated' : 'Copy failed; the previous sound was kept';
        this.syncPresenterState();
      });
    }).catch((error: Error) => {
      this.statusText = `Sound picker failed: ${error.message}`;
    });
  }

  private syncPresenterState(): void {
    this.messageSound = this.presenter.snapshot.messageSound.copy();
    this.callRingtone = this.presenter.snapshot.callRingtone.copy();
    this.showMessageDialog = this.presenter.showMessageSoundDialog;
    this.showCallDialog = this.presenter.showCallRingtoneDialog;
    this.messageError = this.presenter.messageCopyError;
    this.callError = this.presenter.callCopyError;
  }
}
