package org.signal.benchmark.waveform.evaluator;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONException;
import org.json.JSONObject;
import org.signal.benchmark.waveform.VoiceWaveformActivity;
import org.signal.benchmark.waveform.WaveformPageOwner;

public final class VoiceWaveformInstrumentation extends Instrumentation {
  private Bundle arguments;

  @Override public void onCreate(Bundle arguments) {
    super.onCreate(arguments);
    this.arguments = arguments == null ? Bundle.EMPTY : arguments;
    start();
  }

  @Override public void onStart() {
    VoiceWaveformActivity activity = null;
    try {
      String key = required("caseKey");
      JSONObject given = decode(required("given"));
      JSONObject event = decode(required("event"));
      Intent intent = new Intent(Intent.ACTION_MAIN)
          .setClassName(getTargetContext().getPackageName(), VoiceWaveformActivity.class.getName())
          .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
      activity = (VoiceWaveformActivity) startActivitySync(intent);
      VoiceWaveformActivity target = activity;
      onMain(() -> target.prepare(given));
      WaveformPageOwner owner = activity.owner();
      JSONObject before = owner.snapshot();
      AtomicReference<JSONObject> checkpoint = new AtomicReference<>(new JSONObject());
      switch (key) {
        case "generate_upload_ready_waveform" -> onMain(() -> owner.generateWaveform(fullScale(), 2_000_000L));
        case "audio_upload_waits_for_waveform" -> {
          onMain(owner::startUploadGraph);
          checkpoint.set(owner.snapshot());
          onMain(() -> owner.releaseHeldWaveform(fullScale(), 2_000_000L));
        }
        case "mixed_uploads_gate_only_audio" -> {
          onMain(owner::startMixedUploadGraph);
          checkpoint.set(owner.snapshot());
          onMain(() -> owner.releaseMixedAudio(fullScale(), 2_000_000L));
        }
        case "outgoing_pointer_carries_waveform" -> onMain(owner::serializeOutgoingPointer);
        case "reject_oversized_remote_waveform" -> onMain(owner::validateIncomingEnvelope);
        case "persist_valid_sender_waveform" -> onMain(owner::importIncomingAttachment);
        case "resample_sender_waveform_without_media" -> onMain(() -> owner.requestRenderableWaveform(fullScale(), 10_000_000L));
        case "regenerate_stale_local_waveform" -> onMain(() -> owner.requestRenderableWaveform(fullScale(), 2_000_000L));
        case "recover_empty_generation_placeholder" -> onMain(() -> owner.requestRenderableWaveform(silenceThenFullScale(), 4_000_000L));
        case "backup_round_trip_sender_waveform" -> onMain(owner::backupRestoreAndRender);
        default -> throw new IllegalArgumentException("Unknown evaluator case: " + key);
      }
      onMain(target::syncSurface);
      JSONObject after = owner.snapshot();
      JSONObject episode = new JSONObject()
          .put("schemaVersion", 1)
          .put("taskId", "07_voice_note_waveforms")
          .put("key", key)
          .put("given", given)
          .put("event", event)
          .put("givenEstablished", true)
          .put("pageOwnerId", activity.pageOwnerId())
          .put("before", before)
          .put("checkpoint", checkpoint.get())
          .put("after", after)
          .put("observed", after)
          .put("productionCalls", after.getJSONArray("productionCalls"))
          .put("transitionExecuted", true)
          .put("storageReopened", true);
      try (java.io.FileOutputStream output = getTargetContext().openFileOutput("runtime-episode.json", 0)) {
        output.write(episode.toString().getBytes(StandardCharsets.UTF_8));
      }
      activity.finish();
      finish(0, new Bundle());
    } catch (Exception error) {
      if (activity != null) activity.finish();
      Bundle result = new Bundle();
      result.putString("error", error.toString());
      finish(1, result);
    }
  }

  private String required(String name) {
    String value = arguments.getString(name);
    if (value == null) throw new IllegalArgumentException(name + " missing");
    return value;
  }

  private static JSONObject decode(String value) throws JSONException {
    byte[] bytes = Base64.decode(value, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
    return new JSONObject(new String(bytes, StandardCharsets.UTF_8));
  }

  private void onMain(ThrowingRunnable action) throws Exception {
    AtomicReference<Exception> failure = new AtomicReference<>();
    runOnMainSync(() -> {
      try { action.run(); } catch (Exception error) { failure.set(error); }
    });
    if (failure.get() != null) throw failure.get();
    waitForIdleSync();
  }

  private static int[] fullScale() {
    int[] samples = new int[100];
    java.util.Arrays.fill(samples, 32767);
    return samples;
  }

  private static int[] silenceThenFullScale() {
    int[] samples = new int[100];
    java.util.Arrays.fill(samples, 50, 100, 32767);
    return samples;
  }

  private interface ThrowingRunnable { void run() throws Exception; }
}
