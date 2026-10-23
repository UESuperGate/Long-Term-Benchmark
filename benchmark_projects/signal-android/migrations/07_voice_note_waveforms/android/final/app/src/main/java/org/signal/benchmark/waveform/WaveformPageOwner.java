package org.signal.benchmark.waveform;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public final class WaveformPageOwner {
  private static final int STORED_BAR_COUNT = 100;
  private static final int RENDER_BAR_COUNT = 46;
  private final SharedPreferences preferences;
  private JSONObject input = new JSONObject();
  private JSONObject state = new JSONObject();
  private JSONArray effects = new JSONArray();
  private JSONArray productionCalls = new JSONArray();
  private String heldAudioId;

  public WaveformPageOwner(Context context) {
    preferences = context.getSharedPreferences("voice-waveform", Context.MODE_PRIVATE);
  }

  public void mount(JSONObject given) throws JSONException {
    input = cloneObject(given);
    state = new JSONObject();
    effects = new JSONArray();
    productionCalls = new JSONArray();
    heldAudioId = null;
    preferences.edit().clear().commit();
    JSONObject attachment = given.optJSONObject("attachment");
    if (attachment != null) {
      state.put("attachmentId", attachment.optString("id"));
      JSONObject stored = attachment.optJSONObject("storedWaveform");
      if (stored != null) persistRecord(recordFromStored(stored, stored.optBoolean("senderProvided", false)));
    }
    call("WaveformPageOwner.mount");
  }

  public void generateWaveform(int[] decodedPcm, long durationUs) throws JSONException {
    call("WaveformPageOwner.generateWaveform");
    effect("persistGenerationPlaceholder", attachmentId());
    persistRecord(emptyRecord(false));
    effect("decodeAudio", attachmentId());
    JSONObject record = generatedRecord(decodedPcm, durationUs);
    persistRecord(record);
    effect("persistGeneratedWaveform", attachmentId());
    state.put("result", "success");
    state.put("storedWaveform", record);
  }

  public void startUploadGraph() throws JSONException {
    call("WaveformPageOwner.startUploadGraph");
    JSONObject attachment = input.getJSONObject("attachment");
    String id = attachment.getString("id");
    effect("compressAttachment", id);
    JSONObject upload = new JSONObject().put("compression", "complete");
    if (isAudio(attachment.optString("contentType"))) {
      heldAudioId = id;
      upload.put("waveformGeneration", "running").put("upload", "not_started");
      effect("generateWaveform", id);
    } else {
      upload.put("waveformGeneration", "not_scheduled").put("upload", "complete");
      effect("uploadAttachment", id);
    }
    state.put("upload", upload);
  }

  public void releaseHeldWaveform(int[] decodedPcm, long durationUs) throws JSONException {
    call("WaveformPageOwner.releaseHeldWaveform");
    if (heldAudioId == null) return;
    persistRecord(generatedRecord(decodedPcm, durationUs));
    effect("uploadAttachment", heldAudioId);
    state.getJSONObject("upload").put("waveformGeneration", "complete").put("upload", "complete");
    heldAudioId = null;
  }

  public void startMixedUploadGraph() throws JSONException {
    call("WaveformPageOwner.startMixedUploadGraph");
    JSONObject uploads = new JSONObject();
    JSONArray attachments = input.getJSONArray("attachments");
    for (int i = 0; i < attachments.length(); i++) {
      JSONObject attachment = attachments.getJSONObject(i);
      String id = attachment.getString("id");
      effect("compressAttachment", id);
      JSONObject item = new JSONObject().put("compression", "complete");
      if (isAudio(attachment.getString("contentType"))) {
        heldAudioId = id;
        item.put("waveformGeneration", "running").put("upload", "not_started");
        effect("generateWaveform", id);
      } else {
        item.put("waveformGeneration", "not_scheduled").put("upload", "complete");
        effect("uploadAttachment", id);
      }
      uploads.put(id, item);
    }
    state.put("uploads", uploads);
  }

  public void releaseMixedAudio(int[] decodedPcm, long durationUs) throws JSONException {
    call("WaveformPageOwner.releaseMixedAudio");
    if (heldAudioId == null) return;
    persistRecord(generatedRecord(decodedPcm, durationUs));
    effect("uploadAttachment", heldAudioId);
    state.getJSONObject("uploads").getJSONObject(heldAudioId)
        .put("waveformGeneration", "complete").put("upload", "complete");
    heldAudioId = null;
  }

  public void serializeOutgoingPointer() throws JSONException {
    call("WaveformPageOwner.serializeOutgoingPointer");
    JSONObject attachment = input.getJSONObject("attachment");
    JSONObject record = readRecord();
    JSONObject pointer = new JSONObject()
        .put("contentType", attachment.getString("contentType"))
        .put("cdnKey", attachment.optString("cdnKey"))
        .put("encryptionDigest", attachment.optString("encryptionDigest"));
    if (record != null) {
      pointer.put("audioWaveform", cloneArray(record.getJSONArray("bytes")));
      if (record.optDouble("durationSeconds", 0) > 0) {
        pointer.put("audioDurationSeconds", record.getDouble("durationSeconds"));
      }
    }
    effect("buildAttachmentPointer", attachment.getString("id"));
    state.put("pointer", pointer);
  }

  public void validateIncomingEnvelope() throws JSONException {
    call("WaveformPageOwner.validateIncomingEnvelope");
    JSONObject pointer = input.getJSONObject("incomingEnvelope").getJSONObject("attachmentPointer");
    int count = waveformBytes(pointer.opt("audioWaveform")).length();
    boolean accepted = count <= 100;
    state.put("validation", new JSONObject()
        .put("accepted", accepted)
        .put("reason", accepted ? JSONObject.NULL : "oversized_audio_waveform"));
  }

  public void importIncomingAttachment() throws JSONException {
    call("WaveformPageOwner.importIncomingAttachment");
    JSONObject pointer = input.getJSONObject("incomingAttachmentPointer");
    JSONObject record = new JSONObject()
        .put("bytes", waveformBytes(pointer.opt("audioWaveform")))
        .put("barCount", waveformBytes(pointer.opt("audioWaveform")).length())
        .put("durationSeconds", pointer.optDouble("audioDurationSeconds", 0))
        .put("durationUs", Math.round(pointer.optDouble("audioDurationSeconds", 0) * 1_000_000d))
        .put("senderProvided", true);
    persistRecord(record);
    state.put("persistedAttachment", new JSONObject().put("contentType", pointer.getString("contentType")).put("waveform", cloneObject(record)));
    state.put("reloadedAttachment", new JSONObject().put("waveform", readRecord()));
    effect("persistAttachment", pointer.optString("cdnKey"));
  }

  public void requestRenderableWaveform(int[] decodedPcm, long durationUs) throws JSONException {
    call("WaveformPageOwner.requestRenderableWaveform");
    JSONObject attachment = input.getJSONObject("attachment");
    JSONObject record = readRecord();
    boolean localReadable = "readable".equals(attachment.optString("localMedia"));
    if (record == null && !localReadable) {
      state.put("result", "error");
      return;
    }
    boolean senderProvided = record != null && record.optBoolean("senderProvided", false);
    int count = record == null ? 0 : record.optInt("barCount", 0);
    if (!senderProvided && count != STORED_BAR_COUNT) {
      effect("generateWaveform", attachment.getString("id"));
      record = generatedRecord(decodedPcm, durationUs);
      persistRecord(record);
      effect("persistGeneratedWaveform", attachment.getString("id"));
      state.put("persistedReplacement", cloneObject(record));
    }
    if (record == null || record.getJSONArray("bytes").length() == 0) {
      state.put("result", "error");
      return;
    }
    state.put("result", "success");
    state.put("renderWaveform", render(record.getJSONArray("bytes")));
    state.put("durationSeconds", record.optDouble("durationSeconds", 0));
  }

  public void backupRestoreAndRender() throws JSONException {
    call("WaveformPageOwner.backupRestoreAndRender");
    JSONObject attachment = input.getJSONObject("attachment");
    JSONObject record = readRecord();
    JSONObject pointer = new JSONObject().put("contentType", attachment.getString("contentType"));
    if (record != null) {
      pointer.put("audioWaveform", cloneArray(record.getJSONArray("bytes")))
          .put("audioDurationSeconds", record.optDouble("durationSeconds", 0));
    }
    state.put("exportedFilePointer", cloneObject(pointer));
    preferences.edit().clear().commit();
    JSONObject restored = new JSONObject()
        .put("bytes", waveformBytes(pointer.opt("audioWaveform")))
        .put("barCount", waveformBytes(pointer.opt("audioWaveform")).length())
        .put("durationSeconds", pointer.optDouble("audioDurationSeconds", 0))
        .put("durationUs", Math.round(pointer.optDouble("audioDurationSeconds", 0) * 1_000_000d))
        .put("senderProvided", true);
    persistRecord(restored);
    state.put("restoredAttachment", new JSONObject().put("waveform", cloneObject(restored)));
    state.put("renderAfterRestore", new JSONObject().put("result", "success")
        .put("bars", render(restored.getJSONArray("bytes"))));
    effect("exportAttachment", attachment.getString("id"));
    effect("restoreAttachment", attachment.getString("id"));
  }

  public JSONObject snapshot() throws JSONException {
    JSONObject persistence = new JSONObject();
    JSONObject stored = readRecord();
    if (stored != null) persistence.put("waveform", stored);
    return new JSONObject()
        .put("state", cloneObject(state))
        .put("persistence", persistence)
        .put("effects", cloneArray(effects))
        .put("productionCalls", cloneArray(productionCalls));
  }

  private JSONObject generatedRecord(int[] samples, long durationUs) throws JSONException {
    JSONArray bars = new JSONArray();
    for (int bar = 0; bar < STORED_BAR_COUNT; bar++) {
      int start = (int) ((long) bar * samples.length / STORED_BAR_COUNT);
      int end = Math.min(samples.length, Math.max(start + 1, (int) ((long) (bar + 1) * samples.length / STORED_BAR_COUNT)));
      double sum = 0;
      for (int i = start; i < end; i++) sum += (double) samples[i] * samples[i];
      double rms = end > start ? Math.sqrt(sum / (end - start)) / 32767d : 0;
      double db = rms <= 0 ? -60d : 20d * Math.log10(rms);
      double normalized = Math.max(0d, db + 60d) / 60d;
      bars.put((int) Math.round(Math.min(1d, normalized) * 255d));
    }
    return new JSONObject().put("bytes", bars).put("barCount", bars.length())
        .put("durationUs", durationUs).put("durationSeconds", durationUs / 1_000_000d)
        .put("senderProvided", false);
  }

  private JSONArray render(JSONArray source) throws JSONException {
    JSONArray output = new JSONArray();
    for (int bar = 0; bar < RENDER_BAR_COUNT; bar++) {
      int start = (int) ((long) bar * source.length() / RENDER_BAR_COUNT);
      int end = Math.min(source.length(), Math.max(start + 1, (int) ((long) (bar + 1) * source.length() / RENDER_BAR_COUNT)));
      double sum = 0;
      for (int i = start; i < end; i++) sum += source.getInt(i);
      output.put(sum / (end - start) / 255d);
    }
    return output;
  }

  private JSONObject recordFromStored(JSONObject stored, boolean senderProvided) throws JSONException {
    JSONArray bytes = stored.has("bytes") ? cloneArray(stored.getJSONArray("bytes")) : waveformBytes(stored);
    double seconds = stored.has("durationSeconds") ? stored.getDouble("durationSeconds") : stored.optLong("durationUs", 0) / 1_000_000d;
    return new JSONObject().put("bytes", bytes).put("barCount", bytes.length())
        .put("durationSeconds", seconds).put("durationUs", Math.round(seconds * 1_000_000d))
        .put("senderProvided", senderProvided);
  }

  private JSONArray waveformBytes(Object value) throws JSONException {
    if (value instanceof JSONArray) return cloneArray((JSONArray) value);
    if (value instanceof JSONObject) {
      JSONObject source = (JSONObject) value;
      if (source.has("bytes")) return cloneArray(source.getJSONArray("bytes"));
      JSONArray result = new JSONArray();
      JSONArray segments = source.optJSONArray("segments");
      if (segments != null) {
        for (int i = 0; i < segments.length(); i++) {
          JSONObject segment = segments.getJSONObject(i);
          for (int j = 0; j < segment.getInt("count"); j++) result.put(segment.getInt("value"));
        }
        return result;
      }
      int count = source.optInt("barCount", 0);
      int fill = source.optInt("fill", 0);
      for (int i = 0; i < count; i++) result.put(fill);
      return result;
    }
    return new JSONArray();
  }

  private JSONObject emptyRecord(boolean senderProvided) throws JSONException {
    return new JSONObject().put("bytes", new JSONArray()).put("barCount", 0)
        .put("durationUs", 0).put("durationSeconds", 0).put("senderProvided", senderProvided);
  }

  private void persistRecord(JSONObject record) {
    preferences.edit().putString("waveform", record.toString()).commit();
  }

  private JSONObject readRecord() throws JSONException {
    String raw = preferences.getString("waveform", null);
    return raw == null ? null : new JSONObject(raw);
  }

  private String attachmentId() { return input.optJSONObject("attachment").optString("id"); }
  private boolean isAudio(String type) { return type.startsWith("audio/"); }
  private void call(String name) { productionCalls.put(name); }
  private void effect(String name, String id) throws JSONException {
    effects.put(new JSONObject().put("name", name).put("attachmentId", id));
  }
  private static JSONObject cloneObject(JSONObject value) throws JSONException { return new JSONObject(value.toString()); }
  private static JSONArray cloneArray(JSONArray value) throws JSONException { return new JSONArray(value.toString()); }
}
