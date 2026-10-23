package org.thoughtcrime.securesms.video;
import java.util.List;
public final class TranscodingQuality {
  public static int bitRate(long size, long duration) { return 1; }
  public static TranscodingQuality createFromQualityTiers(List<TranscodingConfig.QualityTier> tiers, long duration) { return new TranscodingQuality(); }
  public static TranscodingQuality createManuallyForTesting(String codec, int edge, int video, int audio, long duration) { return new TranscodingQuality(); }
  public int getTargetTotalBitRate() { return 1000; }
  public int getTargetVideoBitRate() { return 800; }
  public int getTargetAudioBitRate() { return 200; }
  public int getOutputResolution() { return 720; }
  public long getByteCountEstimate() { return 1; }
  public String getCodec() { return "video/avc"; }
}
