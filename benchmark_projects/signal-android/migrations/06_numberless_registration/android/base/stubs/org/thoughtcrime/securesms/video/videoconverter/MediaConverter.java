package org.thoughtcrime.securesms.video.videoconverter;
import com.google.common.io.CountingOutputStream;
public class MediaConverter {
  public static final String VIDEO_CODEC_H264 = "video/avc";
  public @interface VideoCodec {}
  public static boolean lastSkipAudio;
  public static boolean converted;
  public interface Listener { boolean onProgress(int percent); }
  public void setInput(Object input) {}
  public void setOutput(CountingOutputStream output) {}
  public void setVideoCodec(String codec) {}
  public void setVideoResolution(int resolution) {}
  public void setVideoBitrate(int bitrate) {}
  public void setAudioBitrate(int bitrate) {}
  public void setAllowAudioRemux(boolean value) {}
  public void setSkipAudio(boolean value) { lastSkipAudio = value; }
  public void setTimeRange(long from, long to) {}
  public void setListener(Listener listener) {}
  public long convert() { converted = true; return 1L; }
  public static void reset() { lastSkipAudio = false; converted = false; }
}
