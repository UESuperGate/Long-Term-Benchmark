package android.net;

import java.util.Objects;

public class Uri {
  private final String value;

  public Uri(String value) {
    this.value = value;
  }

  public static Uri parse(String value) {
    return new Uri(value);
  }

  @Override
  public boolean equals(Object other) {
    return other instanceof Uri && Objects.equals(value, ((Uri) other).value);
  }

  @Override
  public int hashCode() {
    return Objects.hashCode(value);
  }

  @Override
  public String toString() {
    return value;
  }
}
