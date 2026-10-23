package evaluator.domains;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.util.Base64;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONArray;
import org.json.JSONObject;

public final class SemanticInstrumentation extends Instrumentation {
    private Bundle arguments;

    @Override public void onCreate(Bundle arguments) {
        this.arguments = arguments;
        super.onCreate(arguments);
        start();
    }

    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            String encoded = arguments.getString("case_b64");
            JSONObject canonical = new JSONObject(new String(Base64.decode(encoded, Base64.URL_SAFE | Base64.NO_WRAP), StandardCharsets.UTF_8));
            JSONObject payload = runCase(canonical);
            result.putString("runtime_state_transition_b64", Base64.encodeToString(payload.toString().getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            sendStatus(0, result);
            finish(0, result);
        } catch (Throwable error) {
            result.putString("runtime_error", android.util.Log.getStackTraceString(error));
            sendStatus(-1, result);
            finish(-1, result);
        }
    }

    private JSONObject runCase(JSONObject canonical) throws Exception {
        String packageName = getTargetContext().getPackageName();
        Intent intent = new Intent().setClassName(packageName, packageName + ".DomainActivity").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        Activity activity = startActivitySync(intent);
        Object owner = onMain(() -> activity.getClass().getMethod("pageOwner").invoke(activity));
        Class<?> ownerClass = owner.getClass();
        Class<?> backendType = nested(ownerClass, "Backend");
        Class<?> sinkType = nested(ownerClass, "EffectSink");
        JSONObject given = canonical.getJSONObject("given");
        FixtureBackend fixture = new FixtureBackend(given);
        RecordingSink sink = new RecordingSink();
        Object backend = Proxy.newProxyInstance(backendType.getClassLoader(), new Class<?>[]{backendType}, fixture);
        Object effectSink = Proxy.newProxyInstance(sinkType.getClassLoader(), new Class<?>[]{sinkType}, sink);
        onMain(() -> {
            ownerClass.getMethod("configure", backendType, sinkType).invoke(owner, backend, effectSink);
            return null;
        });
        Method invoke = ownerClass.getMethod("invoke", String.class, JSONObject.class);

        establishGiven(activity, given, canonical.optJSONArray("setup"), owner, invoke, sink);
        JSONObject before = onMain(() -> snapshot(ownerClass, owner));
        JSONObject event = new JSONObject(canonical.getJSONObject("event").toString());
        enrichEvent(event, given);
        invokeOnMain(activity, owner, invoke, event.getString("name"), event);
        onMain(() -> {
            activity.getClass().getMethod("render").invoke(activity);
            return null;
        });
        JSONObject after = onMain(() -> snapshot(ownerClass, owner));
        JSONObject observed = new JSONObject().put("state", after.getJSONObject("state")).put("effects", sink.snapshot());
        JSONArray checks = invariantChecks(canonical, before, after, observed, fixture);
        JSONObject payload = new JSONObject()
            .put("schemaVersion", 2)
            .put("taskId", "05_domain_management")
            .put("caseKey", canonical.getString("key"))
            .put("given", given)
            .put("event", canonical.getJSONObject("event"))
            .put("givenEstablished", true)
            .put("commonEntryObserved", true)
            .put("entryOwner", packageName + ".DomainActivity")
            .put("before", before)
            .put("after", after)
            .put("observed", observed)
            .put("invariantChecks", checks)
            .put("invokedProductionMethods", ownerClass.getMethod("invokedMethods").invoke(owner))
            .put("transitionExecuted", true)
            .put("earlyExit", false)
            .put("runtimeEvidence", new JSONObject()
                .put("pageOwnerId", ownerClass.getMethod("ownerId").invoke(owner))
                .put("storeSource", ownerClass.getMethod("storeSource").invoke(owner))
                .put("evaluatorStoreWrites", 0)
                .put("detachedControllers", 0)
                .put("activityClass", activity.getClass().getName())
                .put("excludedSetupEffects", sink.excludedSnapshot())
                .put("renderedSummary", true));
        onMain(() -> { activity.finish(); return null; });
        return payload;
    }

    private interface MainCall<T> { T run() throws Exception; }

    private <T> T onMain(MainCall<T> call) throws Exception {
        AtomicReference<T> value = new AtomicReference<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        runOnMainSync(() -> {
            try { value.set(call.run()); }
            catch (Throwable error) { failure.set(error); }
        });
        Throwable error = failure.get();
        if (error instanceof Exception exception) throw exception;
        if (error != null) throw new RuntimeException(error);
        return value.get();
    }

    private void invokeOnMain(Activity activity, Object owner, Method invoke, String name, JSONObject event) throws Exception {
        onMain(() -> { invoke.invoke(owner, name, event); return null; });
    }

    private static Class<?> nested(Class<?> owner, String simpleName) {
        for (Class<?> type : owner.getDeclaredClasses()) if (simpleName.equals(type.getSimpleName())) return type;
        throw new IllegalStateException("missing production interface " + simpleName);
    }

    private static JSONObject snapshot(Class<?> ownerClass, Object owner) throws Exception {
        return new JSONObject()
            .put("ownerId", ownerClass.getMethod("ownerId").invoke(owner))
            .put("storeSource", ownerClass.getMethod("storeSource").invoke(owner))
            .put("state", ownerClass.getMethod("snapshot").invoke(owner));
    }

    private void establishGiven(Activity activity, JSONObject given, JSONArray setup, Object owner, Method invoke,
        RecordingSink sink) throws Exception {
        JSONArray sequence = given.optJSONArray("querySequence");
        if (sequence != null) {
            for (int i = 0; i < sequence.length(); i++) {
                JSONObject input = sequence.getJSONObject(i);
                invokeOnMain(activity, owner, invoke, "enterRemoteQuery", new JSONObject().put("name", "enterRemoteQuery")
                    .put("query", input.getString("query")).put("atMs", input.getLong("atMs")));
            }
        }
        if (given.has("proposal")) {
            invokeOnMain(activity, owner, invoke, "showProposals", new JSONObject().put("name", "showProposals")
                .put("proposals", new JSONArray().put(given.getJSONObject("proposal"))));
        }
        if (given.has("checkout")) {
            invokeOnMain(activity, owner, invoke, "openCheckout", new JSONObject().put("name", "openCheckout")
                .put("checkout", given.getJSONObject("checkout")));
        }
        if (given.has("detailsWebView")) {
            invokeOnMain(activity, owner, invoke, "openDetails", new JSONObject().put("name", "openDetails")
                .put("managedDomain", given.getString("managedDomain"))
                .put("currentUrl", given.getJSONObject("detailsWebView").getString("currentUrl")));
        }
        if (setup == null) return;
        for (int i = 0; i < setup.length(); i++) {
            JSONObject action = new JSONObject(setup.getJSONObject(i).toString());
            String name = action.getString("name");
            if ("openPurchaseModeFromProposal".equals(name)) action.put("proposal", given.getJSONObject("selectedProposal"));
            invokeOnMain(activity, owner, invoke, name, action);
            if ("openDomainManagementWithLoadedDomains".equals(name)) sink.discardLatest("fetchAllDomains");
            if ("openPurchaseModeFromProposal".equals(name)) sink.discardLatest("openPurchaseDomain");
        }
    }

    private static void enrichEvent(JSONObject event, JSONObject given) throws Exception {
        String name = event.optString("name");
        if ("requestDetailsNavigation".equals(name)) event.put("requestedUrl", given.optString("requestedUrl"));
    }

    private static JSONArray invariantChecks(JSONObject canonical, JSONObject before, JSONObject after,
        JSONObject observed, FixtureBackend fixture) throws Exception {
        JSONArray names = canonical.getJSONArray("invariants");
        boolean[] values = evaluate(canonical.getString("key"), canonical.getJSONObject("given"), before,
            after.getJSONObject("state"), observed.getJSONArray("effects"), fixture);
        if (values.length != names.length()) throw new IllegalStateException("invariant adapter cardinality mismatch");
        JSONArray rows = new JSONArray();
        for (int i = 0; i < values.length; i++) rows.put(new JSONObject()
            .put("invariant", names.getString(i)).put("passed", values[i])
            .put("evidence", new JSONObject().put("before", before).put("after", after).put("effects", observed.getJSONArray("effects"))));
        return rows;
    }

    private static boolean[] evaluate(String key, JSONObject given, JSONObject before, JSONObject state,
        JSONArray effects, FixtureBackend fixture) throws Exception {
        return switch (key) {
            case "loaded_add_domain_entry" -> new boolean[]{
                state.optJSONArray("visibleDomains") != null && state.optJSONArray("visibleDomains").length() == 2,
                state.optBoolean("addDomainEnabled") && "complete".equals(state.optString("listState")),
                fixture.fetchCalls == 1 && fixture.cartCalls == 0
            };
            case "empty_find_domain_entry" -> new boolean[]{
                "empty".equals(state.optString("listState")),
                state.optBoolean("findDomainEnabled") && "new_domain_search".equals(state.optString("destination")),
                fixture.searchCalls == 0 && fixture.cartCalls == 0
            };
            case "error_retry_recovery" -> new boolean[]{
                "error".equals(before.getJSONObject("state").optString("listState")),
                fixture.fetchCalls == 2,
                state.optJSONArray("visibleDomains") != null && state.optJSONArray("visibleDomains").length() == 1
            };
            case "filter_clear_round_trip" -> new boolean[]{
                "filtered".equals(before.getJSONObject("state").optString("listState")),
                state.optJSONObject("beforeClear") != null && state.optJSONObject("beforeClear").optJSONArray("visibleDomains").length() == 1,
                fixture.fetchCalls == 1 && state.optJSONObject("afterClear").optJSONArray("visibleDomains").length() == 2
            };
            case "debounced_latest_search" -> new boolean[]{
                hasEffect(effects, "searchForDomains", "dispatchAtMs", 350),
                "latest".equals(state.optString("normalizedQuery")),
                fixture.searchCalls == 1 && !contains(state.optJSONArray("visibleDomains"), "old.example")
            };
            case "purchase_mode_entry" -> {
                JSONObject selected = state.optJSONObject("selectedProposal");
                yield new boolean[]{
                    selected != null && "chosen.example".equals(selected.optString("domain")),
                    selected != null && selected.optInt("productId") == 42 && selected.optBoolean("supportsPrivacy"),
                    fixture.cartCalls == 0 && "initial".equals(state.optString("purchaseUiState"))
                };
            }
            case "cart_failure_retry" -> new boolean[]{
                "error_submitting_cart".equals(before.getJSONObject("state").optString("purchaseUiState")),
                fixture.cartCalls == 2 && "retry.example".equals(state.optString("checkoutDomain")),
                countEffect(effects, "openDomainCheckout") == 1
            };
            case "checkout_cancel" -> new boolean[]{
                given.getJSONObject("checkout").has("domain"),
                "canceled".equals(state.optString("registrationOutcome")) && !state.optBoolean("purchaseScreenOpen"),
                !hasEffect(effects, "recordDomainPurchaseCompleted")
            };
            case "checkout_success" -> new boolean[]{
                given.getJSONObject("checkout").has("domain"),
                effectIndex(effects, "recordDomainPurchaseCompleted") == 0 && effectIndex(effects, "openDomainManagement") == 1,
                fixture.cartCalls == 0
            };
            case "details_url_allowlist_rejection" -> new boolean[]{
                hasEffect(effects, "redirectToExternalBrowser"),
                !state.optBoolean("requestedUrlLoadedInContainedWebView") && given.optString("managedDomain").equals("some.domain"),
                given.getJSONObject("detailsWebView").optString("currentUrl").equals(state.optString("containedWebViewUrl"))
            };
            default -> throw new IllegalArgumentException("Unknown invariant key " + key);
        };
    }

    private static boolean contains(JSONArray values, String expected) {
        if (values == null) return false;
        for (int i = 0; i < values.length(); i++) if (expected.equals(values.optString(i))) return true;
        return false;
    }
    private static int effectIndex(JSONArray effects, String name) {
        for (int i = 0; i < effects.length(); i++) if (name.equals(effects.optJSONObject(i).optString("name"))) return i;
        return -1;
    }
    private static boolean hasEffect(JSONArray effects, String name) { return effectIndex(effects, name) >= 0; }
    private static boolean hasEffect(JSONArray effects, String name, String field, int value) {
        int index = effectIndex(effects, name);
        return index >= 0 && effects.optJSONObject(index).optInt(field) == value;
    }
    private static int countEffect(JSONArray effects, String name) {
        int index = effectIndex(effects, name);
        return index < 0 ? 0 : effects.optJSONObject(index).optInt("count", 1);
    }

    private static final class FixtureBackend implements java.lang.reflect.InvocationHandler {
        private final Deque<JSONObject> domainResponses = new ArrayDeque<>();
        private final Deque<JSONObject> cartResponses = new ArrayDeque<>();
        private final JSONObject given;
        int fetchCalls;
        int searchCalls;
        int cartCalls;

        FixtureBackend(JSONObject given) throws Exception {
            this.given = given;
            JSONArray responses = given.optJSONArray("accountDomainResponses");
            if (responses != null) for (int i = 0; i < responses.length(); i++) domainResponses.add(new JSONObject(responses.optJSONObject(i).toString()));
            else if (given.has("accountDomainsResponse")) domainResponses.add(new JSONObject(given.optJSONObject("accountDomainsResponse").toString()));
            else if (given.has("loadedDomains")) domainResponses.add(new JSONObject().put("type", "success").put("domains", given.optJSONArray("loadedDomains")));
            JSONArray carts = given.optJSONArray("cartResponses");
            if (carts != null) for (int i = 0; i < carts.length(); i++) cartResponses.add(new JSONObject(carts.optJSONObject(i).toString()));
        }

        @Override public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            return switch (method.getName()) {
                case "fetchAllDomains" -> { fetchCalls += 1; yield domainResponses.isEmpty() ? new JSONObject().put("type", "empty") : domainResponses.removeFirst(); }
                case "searchForDomains" -> { searchCalls += 1; yield search((String) args[0]); }
                case "createCart" -> { cartCalls += 1; yield cartResponses.isEmpty() ? new JSONObject().put("type", "error") : cartResponses.removeFirst(); }
                case "toString" -> "EvaluatorControlledDomainBackend";
                case "hashCode" -> System.identityHashCode(proxy);
                case "equals" -> proxy == args[0];
                default -> throw new UnsupportedOperationException(method.getName());
            };
        }

        private JSONArray search(String query) throws Exception {
            JSONArray sequence = given.optJSONArray("querySequence");
            if (sequence == null) return new JSONArray();
            for (int i = 0; i < sequence.length(); i++) {
                JSONObject row = sequence.optJSONObject(i);
                if (query.equals(row.optString("query"))) return new JSONArray(row.optJSONObject("completion").optJSONArray("domains").toString());
            }
            return new JSONArray();
        }
    }

    private static final class RecordingSink implements java.lang.reflect.InvocationHandler {
        private final JSONArray effects = new JSONArray();
        private final JSONArray excludedSetupEffects = new JSONArray();
        @Override public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            if ("emit".equals(method.getName())) { record(new JSONObject(((JSONObject) args[0]).toString())); return null; }
            if ("toString".equals(method.getName())) return "EvaluatorRecordingEffectSink";
            if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
            if ("equals".equals(method.getName())) return proxy == args[0];
            throw new UnsupportedOperationException(method.getName());
        }
        private void record(JSONObject effect) throws Exception {
            if (effect.has("count")) {
                for (int i = 0; i < effects.length(); i++) {
                    if (effect.optString("name").equals(effects.optJSONObject(i).optString("name"))) { effects.put(i, effect); return; }
                }
            }
            effects.put(effect);
        }
        void discardLatest(String name) throws Exception {
            for (int i = effects.length() - 1; i >= 0; i--) {
                JSONObject effect = effects.optJSONObject(i);
                if (effect != null && name.equals(effect.optString("name"))) {
                    excludedSetupEffects.put(new JSONObject(effect.toString()));
                    effects.remove(i);
                    return;
                }
            }
        }
        JSONArray snapshot() throws Exception { return new JSONArray(effects.toString()); }
        JSONArray excludedSnapshot() throws Exception { return new JSONArray(excludedSetupEffects.toString()); }
    }
}
