package org.whispersystems.signalservice.internal.util;

import java.io.IOException;

public final class JsonUtil {
  public static String toJson(Object value) { return value.toString(); }
  public static <T> T fromJson(String value, Class<T> type) throws IOException { throw new IOException("not available in focused runtime"); }
}
