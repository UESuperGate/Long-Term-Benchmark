import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.util.*;
import java.util.regex.Pattern;

/** Read-only desktop JDI probe. No application methods or setters are invoked. */
public class RuntimeStateProbe {
    static String clean(Object value) {
        return String.valueOf(value).replace("\t", " ").replace("\r", " ").replace("\n", " ");
    }
    static void emit(Object... cells) {
        System.out.println(String.join("\t", Arrays.stream(cells).map(RuntimeStateProbe::clean).toList()));
        System.out.flush();
    }
    static String value(Value v) {
        if (v == null) return "null";
        if (v instanceof StringReference s) return "string:" + s.value();
        if (v instanceof ObjectReference o) return o.referenceType().name() + "#" + o.uniqueID();
        return v.toString();
    }
    static void fields(ObjectReference obj, String path, int depth, Set<Long> seen) {
        if (depth < 0 || !seen.add(obj.uniqueID())) return;
        for (Field f : obj.referenceType().allFields()) {
            if (f.isStatic() || f.name().startsWith("shadow$_")) continue;
            // Never emit account credentials during general object inspection.
            if (f.name().toLowerCase().matches(".*(token|password|secret|credential|sessionkey).*$")) continue;
            try {
                Value v = obj.getValue(f);
                emit("FIELD", obj.uniqueID(), path + "." + f.name(), f.typeName(), value(v));
                if (v instanceof ObjectReference child && !(v instanceof StringReference)) {
                    String n = child.referenceType().name();
                    if (n.startsWith("io.element.") || n.startsWith("androidx.compose.runtime.") ||
                        n.startsWith("kotlinx.coroutines.flow.")) fields(child, path + "." + f.name(), depth - 1, seen);
                }
            } catch (RuntimeException ex) { emit("FIELD_ERROR", f.name(), ex.getClass().getName()); }
        }
    }
    public static void main(String[] args) throws Exception {
        AttachingConnector connector = Bootstrap.virtualMachineManager().attachingConnectors().stream()
            .filter(c -> c.name().equals("com.sun.jdi.SocketAttach")).findFirst().orElseThrow();
        Map<String, Connector.Argument> options = connector.defaultArguments();
        options.get("hostname").setValue("127.0.0.1");
        options.get("port").setValue(args[0]);
        options.get("timeout").setValue("10000");
        VirtualMachine vm = connector.attach(options);
        boolean suspended = false;
        try {
            emit("VM", vm.name(), vm.version(), "instances=" + vm.canGetInstanceInfo(),
                "watchModification=" + vm.canWatchFieldModification(), "watchAccess=" + vm.canWatchFieldAccess());
            Pattern filter = Pattern.compile(args.length > 2 ? args[2] : "io\\.element\\..*State.*");
            vm.suspend(); suspended = true;
            List<ReferenceType> types = vm.allClasses().stream().filter(t -> filter.matcher(t.name()).matches()).toList();
            emit("MATCHED_TYPES", types.size());
            for (ReferenceType t : types) {
                emit("TYPE", t.name());
                if (args[1].equals("inventory") || args[1].equals("watch")) continue;
                List<ObjectReference> objects = t.instances(30);
                emit("INSTANCES", t.name(), objects.size(), "limit=30");
                for (ObjectReference obj : objects) {
                    emit("OBJECT", t.name(), obj.uniqueID());
                    fields(obj, t.name(), 2, new HashSet<>());
                }
            }
            if (args[1].equals("watch")) {
                for (ReferenceType t : types) {
                    Field f = t.fieldByName(args[3]);
                    if (f == null) { emit("NO_FIELD", t.name(), args[3]); continue; }
                    ModificationWatchpointRequest req = vm.eventRequestManager().createModificationWatchpointRequest(f);
                    req.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
                    req.enable();
                    emit("WATCH_READY", t.name(), f.name());
                }
            }
            vm.resume(); suspended = false;
            if (args[1].equals("watch")) {
                long deadline = System.currentTimeMillis() + Long.parseLong(args[4]) * 1000;
                while (System.currentTimeMillis() < deadline) {
                    EventSet set = vm.eventQueue().remove(500);
                    if (set == null) continue;
                    try {
                        for (Event ev : set) {
                            if (ev instanceof ModificationWatchpointEvent w) {
                                emit("WRITE", System.currentTimeMillis(), w.object() == null ? "static" : w.object().uniqueID(),
                                    w.field().declaringType().name(), w.field().name(), value(w.valueCurrent()), value(w.valueToBe()), w.location());
                                if (w.valueToBe() instanceof ObjectReference o) fields(o, "newValue", 1, new HashSet<>());
                            }
                        }
                    } finally { set.resume(); }
                }
            }
        } finally {
            if (suspended) vm.resume();
            vm.dispose();
        }
    }
}
