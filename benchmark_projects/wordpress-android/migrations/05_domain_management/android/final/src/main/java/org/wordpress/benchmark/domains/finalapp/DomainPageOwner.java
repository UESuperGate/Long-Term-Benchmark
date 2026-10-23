package org.wordpress.benchmark.domains.finalapp;

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
    private JSONArray proposals = new JSONArray();
    private JSONObject selectedProposal;
    private String latestQuery = "";
    private long latestQueryAtMs;
    private int fetchCount;
    private int cartCount;
    private final List<String> trace = new ArrayList<>();

    public void configure(Backend backend, EffectSink effects) {
        this.backend = backend;
        this.effects = effects;
        state = new JSONObject();
        storedDomains = new JSONArray();
        proposals = new JSONArray();
        selectedProposal = null;
        latestQuery = "";
        latestQueryAtMs = 0;
        fetchCount = 0;
        cartCount = 0;
        trace.clear();
        trace.add("DomainActivity.onCreate");
    }

    public void invoke(String name, JSONObject event) throws Exception {
        trace.add("DomainPageOwner." + name);
        switch (name) {
            case "openDomainManagementThenTapAddDomain" -> openManagementAndSearch(false);
            case "openDomainManagementThenTapFindDomain" -> openManagementAndSearch(true);
            case "openDomainManagement", "openDomainManagementWithLoadedDomains" -> loadDomains();
            case "waitForListError", "waitForFilteredState", "waitForCartError" -> { }
            case "tapRetry" -> retryDomains();
            case "enterLocalFilter" -> enterLocalFilter(event.optString("query"));
            case "clearLocalFilter" -> clearLocalFilter();
            case "enterRemoteQuery" -> enterRemoteQuery(event.optString("query"), event.optLong("atMs"));
            case "advanceControlledClockAndCompleteRequests" -> advanceClock(event.optLong("toMs"));
            case "showProposals" -> showProposals(event.optJSONArray("proposals"));
            case "tapProposedDomain" -> tapProposal(event.optString("domain"));
            case "openPurchaseModeFromProposal" -> openPurchase(event.optJSONObject("proposal"));
            case "selectNewDomainMode" -> selectDomainOnly();
            case "acknowledgeCartErrorThenRetryNewDomain" -> retryDomainOnlyCart();
            case "openCheckout" -> openCheckout(event.optJSONObject("checkout"));
            case "returnCheckoutResult" -> returnCheckout(event.optJSONObject("result"));
            case "openDetails" -> openDetails(event.optString("managedDomain"), event.optString("currentUrl"));
            case "requestDetailsNavigation" -> requestDetailsNavigation(event.optString("requestedUrl"));
            default -> throw new IllegalArgumentException("Unknown domain event " + name);
        }
    }

    private void loadDomains() throws Exception {
        state = new JSONObject().put("listState", "loading");
        JSONObject response = backend.fetchAllDomains();
        fetchCount += 1;
        effects.emit(new JSONObject().put("name", "fetchAllDomains").put("count", fetchCount));
        String type = response.optString("type");
        if ("success".equals(type)) {
            storedDomains = copyArray(response.optJSONArray("domains"));
            state = new JSONObject().put("listState", "complete").put("visibleDomains", domainNames(storedDomains));
        } else if ("empty".equals(type)) {
            storedDomains = new JSONArray();
            state = new JSONObject().put("listState", "empty").put("searchEnabled", false);
        } else {
            state = new JSONObject().put("listState", "error").put("retryVisible", true);
        }
    }

    private void openManagementAndSearch(boolean emptyAction) throws Exception {
        loadDomains();
        String listState = state.optString("listState");
        if (!("complete".equals(listState) || "empty".equals(listState))) return;
        effects.emit(new JSONObject().put("name", "openNewDomainSearch").put("count", 1));
        if (emptyAction) {
            state = new JSONObject().put("listState", "empty").put("searchEnabled", false)
                .put("findDomainEnabled", true).put("destination", "new_domain_search");
        } else {
            state = new JSONObject().put("listState", "complete").put("visibleDomains", domainNames(storedDomains))
                .put("addDomainEnabled", true).put("destination", "new_domain_search");
        }
    }

    private void retryDomains() throws Exception {
        String before = state.optString("listState");
        state = new JSONObject().put("listState", "loading");
        JSONObject response = backend.fetchAllDomains();
        fetchCount += 1;
        effects.emit(new JSONObject().put("name", "fetchAllDomains").put("count", fetchCount));
        if ("success".equals(response.optString("type"))) {
            storedDomains = copyArray(response.optJSONArray("domains"));
            state = new JSONObject().put("statesInOrder", new JSONArray().put(before).put("loading").put("complete"))
                .put("visibleDomains", domainNames(storedDomains)).put("retryVisibleAfterSuccess", false);
        }
    }

    private void enterLocalFilter(String query) throws Exception {
        JSONArray visible = new JSONArray();
        String needle = query.trim().toLowerCase(Locale.ROOT);
        for (int i = 0; i < storedDomains.length(); i++) {
            JSONObject domain = storedDomains.optJSONObject(i);
            if (domain.optString("domain").toLowerCase(Locale.ROOT).contains(needle)
                || domain.optString("siteSlug").toLowerCase(Locale.ROOT).contains(needle)
                || domain.optString("blogName").toLowerCase(Locale.ROOT).contains(needle)) {
                visible.put(domain.optString("domain"));
            }
        }
        state = new JSONObject().put("listState", "filtered").put("visibleDomains", visible).put("query", query);
        effects.emit(new JSONObject().put("name", "filterLoadedDomains").put("normalizedQuery", query));
    }

    private void clearLocalFilter() throws Exception {
        JSONObject before = new JSONObject().put("listState", state.optString("listState"))
            .put("visibleDomains", copyArray(state.optJSONArray("visibleDomains")));
        JSONObject after = new JSONObject().put("listState", "complete")
            .put("visibleDomains", domainNames(storedDomains)).put("query", "");
        state = new JSONObject().put("beforeClear", before).put("afterClear", after);
        effects.emit(new JSONObject().put("name", "restoreCompleteDomainList"));
    }

    private void enterRemoteQuery(String query, long atMs) throws Exception {
        latestQuery = query.trim();
        latestQueryAtMs = atMs;
        state = new JSONObject().put("normalizedQuery", latestQuery).put("searchState", "waiting_for_debounce");
    }

    private void advanceClock(long toMs) throws Exception {
        long dispatchAt = latestQueryAtMs + 250;
        if (latestQuery.isEmpty() || toMs < dispatchAt) return;
        JSONArray found = backend.searchForDomains(latestQuery);
        effects.emit(new JSONObject().put("name", "searchForDomains").put("query", latestQuery)
            .put("dispatchAtMs", dispatchAt).put("count", 1));
        state = new JSONObject().put("normalizedQuery", latestQuery).put("searchState", "populated")
            .put("visibleDomains", copyArray(found));
    }

    private void showProposals(JSONArray values) throws Exception { proposals = copyArray(values); }

    private void tapProposal(String domain) throws Exception {
        for (int i = 0; i < proposals.length(); i++) {
            JSONObject proposal = proposals.optJSONObject(i);
            if (domain.equals(proposal.optString("domain"))) { openPurchase(proposal); return; }
        }
    }

    private void openPurchase(JSONObject proposal) throws Exception {
        selectedProposal = proposal == null ? new JSONObject() : new JSONObject(proposal.toString());
        JSONObject selected = new JSONObject().put("productId", selectedProposal.optInt("productId"))
            .put("domain", selectedProposal.optString("domain"))
            .put("supportsPrivacy", selectedProposal.optBoolean("supportsPrivacy"));
        state = new JSONObject().put("destination", "purchase_domain").put("purchaseUiState", "initial")
            .put("availableModes", new JSONArray().put("new_domain_only").put("existing_site"))
            .put("selectedProposal", selected);
        effects.emit(new JSONObject().put("name", "openPurchaseDomain")
            .put("productId", selectedProposal.optInt("productId"))
            .put("domain", selectedProposal.optString("domain"))
            .put("supportsPrivacy", selectedProposal.optBoolean("supportsPrivacy")));
    }

    private JSONObject submitDomainOnlyCart() throws Exception {
        String domain = selectedProposal.optString("domain");
        cartCount += 1;
        effects.emit(new JSONObject().put("name", "createCart").put("mode", "domain_only").put("domain", domain).put("count", cartCount));
        return backend.createCart("domain_only", domain);
    }

    private void selectDomainOnly() throws Exception {
        state = new JSONObject().put("purchaseUiState", "submitting_domain_only_cart");
        JSONObject response = submitDomainOnlyCart();
        state = new JSONObject().put("purchaseUiState", "error".equals(response.optString("type")) ? "error_submitting_cart" : "initial");
    }

    private void retryDomainOnlyCart() throws Exception {
        String before = state.optString("purchaseUiState");
        state = new JSONObject().put("purchaseUiState", "initial");
        JSONObject response = submitDomainOnlyCart();
        if ("success".equals(response.optString("type"))) {
            String domain = selectedProposal.optString("domain");
            effects.emit(new JSONObject().put("name", "openDomainCheckout").put("domain", domain).put("count", 1));
            state = new JSONObject().put("beforeRetry", before)
                .put("statesAfterEvent", new JSONArray().put("initial").put("submitting_domain_only_cart").put("initial"))
                .put("destination", "domain_checkout").put("checkoutDomain", domain);
        }
    }

    private void openCheckout(JSONObject checkout) throws Exception {
        state = new JSONObject().put("purchaseScreenOpen", true).put("checkout", checkout == null ? new JSONObject() : checkout);
    }

    private void returnCheckout(JSONObject result) throws Exception {
        boolean canceled = result != null && result.optBoolean("canceled");
        if (!canceled) effects.emit(new JSONObject().put("name", "recordDomainPurchaseCompleted"));
        effects.emit(new JSONObject().put("name", "openDomainManagement").put("count", 1));
        state = new JSONObject().put("destination", "all_domains").put("purchaseScreenOpen", false)
            .put("checkoutError", false).put("registrationOutcome", canceled ? "canceled" : "completed");
    }

    private void openDetails(String managedDomain, String currentUrl) throws Exception {
        state = new JSONObject().put("managedDomain", managedDomain).put("containedWebViewUrl", currentUrl)
            .put("requestedUrlLoadedInContainedWebView", false);
    }

    private void requestDetailsNavigation(String requestedUrl) throws Exception {
        String managed = state.optString("managedDomain");
        boolean allowed = false;
        try {
            URI uri = URI.create(requestedUrl);
            allowed = "https".equalsIgnoreCase(uri.getScheme()) && "wordpress.com".equalsIgnoreCase(uri.getHost())
                && uri.getPath().startsWith("/domains/manage/all/" + managed + "/edit/");
        } catch (IllegalArgumentException ignored) { }
        if (allowed) {
            state.put("containedWebViewUrl", requestedUrl).put("requestedUrlLoadedInContainedWebView", true);
        } else {
            effects.emit(new JSONObject().put("name", "redirectToExternalBrowser").put("url", requestedUrl).put("count", 1));
            state = new JSONObject().put("containedWebViewUrl", state.optString("containedWebViewUrl"))
                .put("requestedUrlLoadedInContainedWebView", false);
        }
    }

    private static JSONArray domainNames(JSONArray domains) {
        JSONArray names = new JSONArray();
        if (domains == null) return names;
        for (int i = 0; i < domains.length(); i++) names.put(domains.optJSONObject(i).optString("domain"));
        return names;
    }

    private static JSONArray copyArray(JSONArray value) throws Exception { return value == null ? new JSONArray() : new JSONArray(value.toString()); }
    public JSONObject snapshot() throws Exception { return new JSONObject(state.toString()); }
    public JSONArray invokedMethods() { return new JSONArray(trace); }
    public String ownerId() { return "android-domain-activity-owner"; }
    public String storeSource() { return "DomainActivity.DomainPageOwner"; }
}
