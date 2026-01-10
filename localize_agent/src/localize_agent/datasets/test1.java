package localize_agent.datasets;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

// This file intentionally contains several design issues to exercise the analyzers:
// - Public fields (information hiding violation)
// - Many small and large methods in one class (complexity)
// - Methods that belong in another class (move method candidate)
// - High coupling between classes

public class AdvancedProcessor {

    // Information hiding violation: public fields
    public List<String> inputs = new ArrayList<>();
    public Map<String, Integer> counters = new HashMap<>();
    public int globalCount = 0;

    public AdvancedProcessor() {
        // initialize with some defaults
        counters.put("processed", 0);
    }

    // Complex method with nested loops and branching (complexity)
    public void processAll() {
        for (int i = 0; i < inputs.size(); i++) {
            String item = inputs.get(i);
            // duplicated logic scattered across methods
            if (item == null) continue;
            if (item.contains(".")) {
                String cleaned = cleanup(item);
                transformAndStore(cleaned);
            } else {
                transformAndStore(item);
            }

            // heavy processing block
            for (int pass = 0; pass < 3; pass++) {
                String m = expensiveOperation(item, pass);
                if (m.length() > 0) {
                    counters.put(m, counters.getOrDefault(m, 0) + 1);
                }
            }
            globalCount++;
        }
    }

    // Method that probably belongs to HelperUtils (move method candidate)
    public String cleanup(String s) {
        // mimic complex cleaning with regex-like replacements
        String r = s.replaceAll("\\\n", " ");
        r = r.replaceAll("\\s+", " ");
        r = r.trim();
        return r;
    }

    // Another method that could be elsewhere; relatively small but used across classes
    public void transformAndStore(String s) {
        // store with a naive key generation
        String key = s.length() > 10 ? s.substring(0, 10) : s;
        counters.put(key, counters.getOrDefault(key, 0) + 1);
    }

    private String expensiveOperation(String s, int pass) {
        // intentionally complex string manipulations
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isLetter(c)) sb.append(Character.toLowerCase(c));
            else if (Character.isDigit(c)) sb.append((char)('0' + ((c - '0' + pass) % 10)));
            else sb.append('_');
        }
        return sb.toString();
    }

    // Many small helper methods increasing method count
    public void addInput(String s) { inputs.add(s); }
    public int getGlobalCount() { return globalCount; }
    public void reset() { inputs.clear(); counters.clear(); globalCount = 0; }
    public void printStats() {
        System.out.println("Global count: " + globalCount);
        System.out.println("Counters: " + counters);
    }

    // Duplicate-ish functionality to confuse naive analyzers (another candidate for inlining)
    public int computeSize() {
        int c = 0;
        for (String s : inputs) c += s.length();
        return c;
    }

    public int computeTotalLength() { return computeSize(); }

}


// Another class that tightly couples with AdvancedProcessor
class ExternalCoordinator {

    private AdvancedProcessor proc;

    public ExternalCoordinator(AdvancedProcessor proc) {
        this.proc = proc;
    }

    public void coordinate() {
        // high coupling: directly reads public fields
        if (proc.inputs.size() == 0) return;

        // calls several methods from AdvancedProcessor
        proc.processAll();
        proc.printStats();

        // repeated logic that duplicates AdvancedProcessor behavior
        for (String s : proc.inputs) {
            String key = s.length() > 5 ? s.substring(0,5) : s;
            proc.counters.put(key, proc.counters.getOrDefault(key, 0) + 1);
        }
    }

    public void doWork(String s) {
        // delegates but also manipulates internal data directly
        proc.addInput(s);
        if (proc.globalCount % 5 == 0) proc.reset();
    }
}
