package runtime.task17.connected

import android.app.Application
import android.os.Bundle
import androidx.lifecycle.ProcessLifecycleInitializer
import androidx.startup.AppInitializer
import io.element.android.appnav.LoggedInFlowNode
import io.element.android.libraries.architecture.NodeFactoriesBindings
import io.element.android.libraries.di.DaggerComponentOwner
import io.element.android.libraries.featureflag.api.FeatureFlagService
import io.element.android.libraries.featureflag.api.FeatureFlags
import io.element.android.services.analytics.api.AnalyticsService
import io.element.android.x.di.AppComponent
import io.element.android.x.di.DaggerAppComponent
import io.element.android.x.di.SessionComponent
import io.element.android.x.di.AppModule
import io.element.android.libraries.core.coroutine.CoroutineDispatchers
import io.element.android.libraries.matrix.impl.RustMatrixClient
import io.element.android.libraries.sessionstorage.api.SessionStore
import io.element.android.libraries.sessionstorage.api.SessionData
import io.element.android.libraries.sessionstorage.api.LoginType
import io.element.android.libraries.sessionstorage.impl.memory.InMemorySessionStore
import io.element.android.services.toolbox.impl.systemclock.DefaultSystemClock
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.cancel
import java.lang.reflect.ParameterizedType
import java.security.KeyStore
import java.security.Security
import javax.inject.Provider
import kotlin.reflect.KClass
import kotlin.reflect.full.primaryConstructor

/** The production component owns every internal binding, generated factory and room scope. */
@Suppress("DEPRECATION")
private class Task17AndroidKeyStoreProvider(fallback: java.security.Provider.Service) :
    java.security.Provider("AndroidKeyStore", 1.0, "Task17 Robolectric AndroidKeyStore transport") {
    init {
        putService(java.security.Provider.Service(
            this, "KeyStore", "AndroidKeyStore", fallback.className, emptyList(), emptyMap()
        ))
    }
}

class Task17Application : Application(), DaggerComponentOwner {
    override val daggerComponent: AppComponent by lazy { DaggerAppComponent.factory().create(this) }
    val startupEvidence = linkedMapOf<String, Any?>()
    private var installedAndroidKeyStoreProvider = false

    override fun onCreate() {
        super.onCreate()
        val initializer = AppInitializer.getInstance(this)
        val metadata = Bundle().apply {
            putString(ProcessLifecycleInitializer::class.java.name, getString(androidx.startup.R.string.androidx_startup))
        }
        val discover = AppInitializer::class.java.declaredMethods.single {
            it.name == "discoverAndInitialize" && it.parameterTypes.contentEquals(arrayOf(Bundle::class.java))
        }.apply { isAccessible = true }
        discover.invoke(initializer, metadata)
        check(initializer.isEagerlyInitialized(ProcessLifecycleInitializer::class.java))
        val fallbackType = KeyStore.getDefaultType()
        val fallback = Security.getProviders().asSequence().flatMap { it.services.asSequence() }.first {
            it.type == "KeyStore" && it.algorithm.equals(fallbackType, ignoreCase = true)
        }
        check(Security.getProvider("AndroidKeyStore") == null)
        val providerPosition = Security.insertProviderAt(Task17AndroidKeyStoreProvider(fallback), 1)
        check(providerPosition > 0)
        installedAndroidKeyStoreProvider = true
        startupEvidence += mapOf(
            "initializer" to ProcessLifecycleInitializer::class.java.name,
            "source" to "original app InitializationProvider metadata",
            "method" to discover.name,
            "eager" to true,
            "androidKeyStoreFallbackProvider" to fallback.provider.name,
            "androidKeyStoreFallbackAlgorithm" to fallback.algorithm,
            "androidKeyStoreFallbackClass" to fallback.className,
            "androidKeyStoreProviderPosition" to providerPosition,
        )
    }

    fun removeEvaluatorProvider() {
        if (installedAndroidKeyStoreProvider) {
            Security.removeProvider("AndroidKeyStore")
            installedAndroidKeyStoreProvider = false
            startupEvidence["androidKeyStoreProviderRemoved"] = Security.getProvider("AndroidKeyStore") == null
        }
    }
}

class Task17ProductionBindings(private val application: Task17Application, val sdk: Task17SdkInputs) {
    val app = application.daggerComponent
    lateinit var session: SessionComponent
        private set
    val generatedBindings = mutableListOf<Map<String, Any?>>()

    /** Read generated provider metadata; never synthesize dependencies or call constructors. */
    private fun <T : Any> service(type: Class<T>): T {
        val matches = app.javaClass.declaredFields.mapNotNull { field ->
            val signature = field.genericType as? ParameterizedType ?: return@mapNotNull null
            val raw = signature.rawType as? Class<*> ?: return@mapNotNull null
            if (!Provider::class.java.isAssignableFrom(raw)) return@mapNotNull null
            val provided = signature.actualTypeArguments.singleOrNull() as? Class<*> ?: return@mapNotNull null
            if (!type.isAssignableFrom(provided)) return@mapNotNull null
            field.isAccessible = true
            val result = type.cast((field.get(app) as Provider<*>).get())
            generatedBindings += mapOf("componentClass" to app.javaClass.name,
                "componentId" to System.identityHashCode(app), "field" to field.name,
                "genericSignature" to signature.typeName, "providedClass" to result.javaClass.name,
                "instanceId" to System.identityHashCode(result))
            result
        }.distinctBy { System.identityHashCode(it) }
        return matches.singleOrNull() ?: error("Original generated provider not unique for ${type.name}: ${matches.size}")
    }

    /** Seed one generated Dagger singleton with a version-matched production environment input. */
    private fun seedService(type: Class<*>, value: Any) {
        check(type.isInstance(value)) { "Seed value does not implement ${type.name}" }
        val matches = app.javaClass.declaredFields.mapNotNull { field ->
            val signature = field.genericType as? ParameterizedType ?: return@mapNotNull null
            val raw = signature.rawType as? Class<*> ?: return@mapNotNull null
            if (!Provider::class.java.isAssignableFrom(raw)) return@mapNotNull null
            val provided = signature.actualTypeArguments.singleOrNull() as? Class<*> ?: return@mapNotNull null
            if (!type.isAssignableFrom(provided)) return@mapNotNull null
            field.isAccessible = true
            Triple(field, signature, checkNotNull(field.get(app)))
        }
        val (field, signature, provider) = matches.singleOrNull()
            ?: error("Original generated seed provider not unique for ${type.name}: ${matches.size}")
        check(provider.javaClass.name == "dagger.internal.DoubleCheck") {
            "Unreviewed generated provider wrapper for ${type.name}: ${provider.javaClass.name}"
        }
        val instanceField = provider.javaClass.getDeclaredField("instance").apply { isAccessible = true }
        val delegateField = provider.javaClass.getDeclaredField("provider").apply { isAccessible = true }
        instanceField.set(provider, value)
        delegateField.set(provider, null)
        check((provider as Provider<*>).get() === value) { "Generated provider seed identity mismatch" }
        generatedBindings += mapOf(
            "seededGeneratedProvider" to type.name,
            "componentClass" to app.javaClass.name,
            "componentId" to System.identityHashCode(app),
            "field" to field.name,
            "genericSignature" to signature.typeName,
            "providerClass" to provider.javaClass.name,
            "providedClass" to value.javaClass.name,
            "instanceId" to System.identityHashCode(value),
        )
    }

    private fun original(type: KClass<*>, inputs: Map<String, Any?>): Any {
        check(type.qualifiedName in setOf("io.element.android.libraries.sessionstorage.api.SessionData",
            "io.element.android.libraries.matrix.impl.RustMatrixClient",
            "io.element.android.libraries.matrix.impl.RustClientSessionDelegate"))
        val constructor = checkNotNull(type.primaryConstructor)
        val arguments = constructor.parameters.filter { !it.isOptional || inputs.containsKey(it.name) }.associateWith { parameter ->
            check(inputs.containsKey(parameter.name)) { "Unbound ORIGINAL ${type.qualifiedName}.${parameter.name}" }
            inputs[parameter.name]
        }
        return constructor.callBy(arguments).also { instance ->
            generatedBindings += mapOf("originalConstructor" to type.qualifiedName,
                "parameterNames" to arguments.keys.map { it.name }, "instanceId" to System.identityHashCode(instance))
        }
    }

    suspend fun configureExistingInputs() {
        // Element X ships this production store for runtimes that do not own an Android keystore.
        val store = InMemorySessionStore()
        generatedBindings += mapOf(
            "environmentInput" to "sessionStore",
            "providedClass" to store.javaClass.name,
            "sourceModule" to ":libraries:session-storage:impl-memory",
            "reason" to "Robolectric has no AndroidKeyStore",
            "instanceId" to System.identityHashCode(store),
        )
        seedService(SessionStore::class.java, store)
        val appScope = service(CoroutineScope::class.java)
        val dispatchers = service(CoroutineDispatchers::class.java)
        val base = AppModule.providesBaseDirectory(application)
        val cache = AppModule.providesCacheDirectory(application)
        store.storeData(original(SessionData::class, mapOf("userId" to sdk.userId.value, "deviceId" to "RUNTIME17",
            "accessToken" to "sdk-fixture-not-a-key", "refreshToken" to null, "homeserverUrl" to "https://example.org",
            "oidcData" to null, "slidingSyncProxy" to null, "loginTimestamp" to null, "isTokenValid" to true,
            "loginType" to LoginType.PASSWORD, "passphrase" to null,
            "sessionPath" to java.io.File(base, "runtime17").absolutePath,
            "cachePath" to java.io.File(cache, "runtime17").absolutePath)) as SessionData)
        val parameters = mutableMapOf<String, Any?>("client" to sdk.session.client, "syncService" to sdk.session.sync,
            "sessionStore" to store, "appCoroutineScope" to appScope, "dispatchers" to dispatchers,
            "baseDirectory" to base, "baseCacheDirectory" to cache, "clock" to DefaultSystemClock())
        RustMatrixClient::class.primaryConstructor!!.parameters.singleOrNull { it.name == "sessionDelegate" }?.let { parameter ->
            parameters["sessionDelegate"] = original(parameter.type.classifier as KClass<*>,
                mapOf("sessionStore" to store, "appCoroutineScope" to appScope, "coroutineDispatchers" to dispatchers))
        }
        sdk.bindClient(original(RustMatrixClient::class, parameters) as RustMatrixClient)
        session = (app as SessionComponent.ParentBindings).sessionComponentBuilder().client(sdk.client).build()
        check(service(FeatureFlagService::class.java).setFeatureEnabled(FeatureFlags.PinnedEvents, true)) {
            "Original feature flag store refused setup"
        }
        // A public preference input, not FtueState assignment or an internal service double.
        service(AnalyticsService::class.java).setDidAskUserConsent()
    }

    fun rootFactory() = checkNotNull(session.nodeFactories()[LoggedInFlowNode::class.java]) {
        "Original generated LoggedInFlowNode factory missing"
    }

    fun componentEvidence(): Map<String, Any?> {
        if (!this::session.isInitialized || !sdk.hasBoundClient()) return mapOf(
            "bindingStatus" to "incomplete", "appClass" to app.javaClass.name,
            "androidStartup" to application.startupEvidence.toMap(),
            "resolvedProviders" to generatedBindings.toList())
        return mapOf(
        "appClass" to app.javaClass.name, "appId" to System.identityHashCode(app),
        "androidStartup" to application.startupEvidence.toMap(),
        "sessionClass" to session.javaClass.name, "sessionId" to System.identityHashCode(session),
        "clientId" to System.identityHashCode(sdk.client), "clientClass" to sdk.client.javaClass.name,
        "leafRoomId" to System.identityHashCode(sdk.innerRoom),
        "nodeFactories" to session.nodeFactories().map { (node, factory) ->
            mapOf("node" to node.name, "factory" to factory.javaClass.name,
                "factoryId" to System.identityHashCode(factory))
        }.sortedBy { it["node"].toString() }, "resolvedProviders" to generatedBindings.toList())
    }

    fun cancelOwnedScopes() {
        if (sdk.hasBoundClient()) sdk.client.close()
        // Only this invocation's original components; no process-global or foreign scopes.
        (listOf(app) + if (this::session.isInitialized) listOf(session) else emptyList()).forEach { component ->
            component.javaClass.declaredFields.forEach fields@ { field ->
                val signature = field.genericType as? ParameterizedType ?: return@fields
                val raw = signature.rawType as? Class<*> ?: return@fields
                if (!Provider::class.java.isAssignableFrom(raw) ||
                    signature.actualTypeArguments.singleOrNull() != CoroutineScope::class.java) return@fields
                field.isAccessible = true
                ((field.get(component) as Provider<*>).get() as CoroutineScope).cancel()
            }
        }
    }
}
