package org.wordpress.benchmark.domains.base;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

public final class DomainPageOwner {
    public interface Backend {
        JSONObject fetchAllDomains() throws Exception;
        JSONArray searchForDomains(String query) throws Exception;
        JSONObject createCart(String mode, String domain) throws Exception;
    }
    public interface EffectSink { void emit(JSONObject effect) throws Exception; }

    private Backend backend;
    private EffectSink effects;
    private JSONObject state = new JSONObject();
    private JSONArray storedDomains = new JSONArray();
    private JSONObject selectedProposal;
    private final List<String> trace = new ArrayList<>();

    public void configure(Backend backend, EffectSink effects) {
        this.backend = backend;
        this.effects = effects;
        this.state = new JSONObject();
        this.storedDomains = new JSONArray();
        this.selectedProposal = null;
        this.trace.clear();
        trace.add("DomainActivity.onCreate");
    }

    public void invoke(String name, JSONObject event) throws Exception {
        trace.add("DomainPageOwner." + name);
        switch (name) {
            case "openDomainManagementThenTapAddDomain" -> { loadDomains(); state.put("addDomainEnabled", true); state.put("destination", JSONObject.NULL); }
            case "openDomainManagementThenTapFindDomain" -> { loadDomains(); state.put("findDomainEnabled", true); state.put("destination", JSONObject.NULL); }
            case "openDomainManagement", "openDomainManagementWithLoadedDomains" -> loadDomains();
            case "waitForListError", "waitForFilteredState", "waitForCartError" -> { }
            case "tapRetry" -> { }
            case "enterLocalFilter" -> legacyFilter(event.optString("query"));
            case "clearLocalFilter" -> clearFilter();
            case "enterRemoteQuery", "advanceControlledClockAndCompleteRequests" -> { }
            case "showProposals" -> selectedProposal = event.optJSONObject("proposal");
            case "tapProposedDomain" -> { }
            case "openPurchaseModeFromProposal" -> selectedProposal = event.optJSONObject("proposal");
            case "selectNewDomainMode", "acknowledgeCartErrorThenRetryNewDomain" -> { }
            case "openCheckout" -> state = new JSONObject().put("purchaseScreenOpen", true);
            case "returnCheckoutResult" -> state = new JSONObject().put("purchaseScreenOpen", true).put("registrationOutcome", "unsupported");
            case "openDetails" -> state = new JSONObject().put("containedWebViewUrl", event.optString("currentUrl"));
            case "requestDetailsNavigation" -> state = new JSONObject().put("containedWebViewUrl", event.optString("requestedUrl")).put("requestedUrlLoadedInContainedWebView", true);
            default -> throw new IllegalArgumentException("Unknown domain event " + name);
        }
    }

    private void loadDomains() throws Exception {
        JSONObject response = backend.fetchAllDomains();
        effects.emit(new JSONObject().put("name", "fetchAllDomains").put("count", 1));
        String type = response.optString("type");
        if ("success".equals(type)) {
            storedDomains = response.optJSONArray("domains");
            state = new JSONObject().put("listState", "complete").put("visibleDomains", domainNames(storedDomains));
        } else if ("empty".equals(type)) {
            storedDomains = new JSONArray();
            state = new JSONObject().put("listState", "empty").put("searchEnabled", false);
        } else {
            state = new JSONObject().put("listState", "error");
        }
    }

    private void legacyFilter(String query) throws Exception {
        JSONArray visible = new JSONArray();
        String needle = query.toLowerCase(Locale.ROOT);
        for (int i = 0; i < storedDomains.length(); i++) {
            JSONObject domain = storedDomains.optJSONObject(i);
            if (domain.optString("domain").toLowerCase(Locale.ROOT).contains(needle) || domain.optString("siteSlug").toLowerCase(Locale.ROOT).contains(needle)) {
                visible.put(domain.optString("domain"));
            }
        }
        state = new JSONObject().put("listState", "filtered").put("visibleDomains", visible).put("query", query);
        effects.emit(new JSONObject().put("name", "filterLoadedDomains").put("normalizedQuery", query));
    }

    private void clearFilter() throws Exception {
        JSONObject before = new JSONObject().put("listState", state.optString("listState")).put("visibleDomains", state.optJSONArray("visibleDomains"));
        JSONObject after = new JSONObject().put("listState", "complete").put("visibleDomains", domainNames(storedDomains)).put("query", "");
        state = new JSONObject().put("beforeClear", before).put("afterClear", after);
        effects.emit(new JSONObject().put("name", "restoreCompleteDomainList"));
    }

    private static JSONArray domainNames(JSONArray domains) {
        JSONArray names = new JSONArray();
        if (domains == null) return names;
        for (int i = 0; i < domains.length(); i++) names.put(domains.optJSONObject(i).optString("domain"));
        return names;
    }

    public JSONObject snapshot() throws Exception { return new JSONObject(state.toString()); }
    public JSONArray invokedMethods() { return new JSONArray(trace); }
    public String ownerId() { return "android-domain-activity-owner"; }
    public String storeSource() { return "DomainActivity.DomainPageOwner"; }
}

