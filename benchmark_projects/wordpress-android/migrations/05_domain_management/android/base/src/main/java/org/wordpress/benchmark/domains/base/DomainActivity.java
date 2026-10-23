package org.wordpress.benchmark.domains.base;

import android.app.Activity;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;

public final class DomainActivity extends Activity {
    private DomainPageOwner owner;
    private TextView summary;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        owner = new DomainPageOwner();
        owner.configure(new EmptyBackend(), effect -> { });
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setPadding(32, 32, 32, 32);
        TextView title = new TextView(this);
        title.setText("All Domains");
        title.setTextSize(28);
        summary = new TextView(this);
        try { summary.setText(owner.snapshot().toString()); }
        catch (Exception error) { throw new IllegalStateException(error); }
        column.addView(title);
        column.addView(summary);
        setContentView(column);
    }

    public DomainPageOwner pageOwner() { return owner; }
    public void render() {
        try { summary.setText(owner.snapshot().toString()); }
        catch (Exception error) { throw new IllegalStateException(error); }
    }

    private static final class EmptyBackend implements DomainPageOwner.Backend {
        @Override public JSONObject fetchAllDomains() throws Exception { return new JSONObject().put("type", "empty"); }
        @Override public JSONArray searchForDomains(String query) { return new JSONArray(); }
        @Override public JSONObject createCart(String mode, String domain) throws Exception { return new JSONObject().put("type", "error"); }
    }
}

