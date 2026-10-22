package runtime.task17.connected

import io.element.android.libraries.architecture.Presenter
import java.lang.reflect.InvocationTargetException
import java.lang.reflect.Proxy
import kotlin.reflect.*
import kotlin.reflect.full.*
import kotlin.reflect.jvm.kotlinFunction

/** DI construction only. Unbound interfaces never become permissive doubles. */
class Task17ConstructorGraph(val log: MutableList<Map<String, Any?>>) {
    val values = mutableMapOf<KClass<*>, Any>()
    val typedValues = mutableMapOf<KType, Any>()
    val aliases = mutableMapOf<KClass<*>, KClass<*>>()
    val presenters = mutableMapOf<KClass<*>, KClass<*>>()
    private val scoped = mutableMapOf<KClass<*>, Any>()
    val constructed = mutableListOf<Any>()
    private val resolving = mutableListOf<KClass<*>>()

    fun make(type: KType, assisted: Map<String, Any?> = emptyMap()): Any {
        typedValues[type]?.let { return it }
        val requested = type.classifier as? KClass<*> ?: error("Unbound type parameter: $type")
        values[requested]?.let { return it }
        if (requested == Presenter::class) {
            val state = type.arguments.single().type?.classifier as? KClass<*>
            return make(checkNotNull(presenters[state]) { "Unbound original presenter: $type" }.createType(), assisted)
        }
        val klass = aliases[requested] ?: requested
        if (klass != requested) return make(klass.createType(), assisted)
        if (klass.java.isInterface) {
            val methods = klass.java.declaredMethods.filterNot { it.isDefault }
            check(klass.simpleName == "Factory" && methods.size == 1 && methods.single().name == "create" &&
                methods.single().kotlinFunction?.returnType?.classifier == klass.java.enclosingClass?.kotlin) {
                "Unbound non-constructor interface: ${klass.qualifiedName}"
            }
            return Proxy.newProxyInstance(klass.java.classLoader, arrayOf(klass.java)) { proxy, method, args ->
                when (method.name) {
                    "toString" -> "OriginalFactory:${klass.qualifiedName}"
                    "hashCode" -> System.identityHashCode(proxy)
                    "equals" -> proxy === args?.firstOrNull()
                    else -> {
                        val fn = checkNotNull(method.kotlinFunction)
                        val params = fn.parameters.filter { it.kind == KParameter.Kind.VALUE }
                        val input = params.mapIndexed { index, p -> checkNotNull(p.name) to args?.get(index) }.toMap()
                        make(fn.returnType, input)
                    }
                }
            }
        }
        klass.objectInstance?.let { return it }
        check(klass.qualifiedName?.startsWith("io.element.android.") == true) { "Unbound platform/SDK value: $type" }
        check(klass !in resolving) { "Constructor cycle: $resolving -> $klass" }
        val singleton = assisted.isEmpty() && klass.annotations.any {
            it.annotationClass.qualifiedName in setOf("io.element.android.libraries.di.SingleIn", "javax.inject.Singleton")
        }
        if (singleton) scoped[klass]?.let { return it }
        resolving += klass
        try {
            val constructor = checkNotNull(klass.primaryConstructor) { "No original constructor: $klass" }
            val args = constructor.parameters.filter { !it.isOptional || assisted.containsKey(it.name) }.associateWith { parameter ->
                if (assisted.containsKey(parameter.name)) assisted[parameter.name] else make(parameter.type)
            }
            val value = try { constructor.callBy(args) } catch (e: InvocationTargetException) { throw e.targetException }
            constructed += value
            if (singleton) scoped[klass] = value
            log += mapOf("class" to klass.qualifiedName, "instanceId" to System.identityHashCode(value),
                "dependencies" to args.map { (key, dependency) -> mapOf("name" to key.name,
                    "instanceId" to dependency?.let(System::identityHashCode), "class" to dependency?.javaClass?.name) })
            return value
        } finally { resolving.removeAt(resolving.lastIndex) }
    }
}
