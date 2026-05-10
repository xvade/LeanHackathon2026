/*
 * Native exp08 scorer for neural_grind.
 *
 * This is intentionally narrow: it implements the cheap numeric MLP used by
 * training/experiments/exp08_num_pool_counts.  It avoids Python in the tactic
 * loop while preserving the same line protocol result shape as serve.py:
 *
 *   "<chosen-anchor> <top1-top2-margin-milli>"
 *
 * We parse the compact JSON strings produced in SplitPolicy.lean.  This is not
 * a general JSON parser; it only accepts the known fields emitted there.
 */
#ifndef NEURAL_GRIND_STANDALONE
#include <lean/lean.h>
#endif

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr uint32_t kInputDim = 32;

struct Weights {
    uint32_t input_dim = 0;
    uint32_t hidden_dim = 0;
    std::vector<float> fc1_w;
    std::vector<float> fc1_b;
    std::vector<float> fc2_w;
    std::vector<float> fc2_b;
    std::vector<float> fc3_w;
    float fc3_b = 0.0f;
    bool loaded = false;
};

struct GoalFeatures {
    float splitDepth = 0.0f;
    float assertedCount = 0.0f;
    float ematchRounds = 0.0f;
    float splitTraceLen = 0.0f;
    float numCandidates = 1.0f;
};

struct Candidate {
    uint64_t anchor = 0;
    int numCases = 0;
    bool isRec = false;
    std::string source;
    int generation = 0;
    bool tryPostpone = false;
    std::string variant;
    bool isGrindChoice = false;
};

struct Scored {
    uint64_t anchor = 0;
    float score = 0.0f;
};

static Weights g_weights;
static bool g_load_attempted = false;

static std::string key_pattern(const char* key) {
    return std::string("\"") + key + "\":";
}

static double number_field(const std::string& s, const char* key, double fallback = 0.0) {
    const std::string pat = key_pattern(key);
    size_t p = s.find(pat);
    if (p == std::string::npos) return fallback;
    p += pat.size();
    char* end = nullptr;
    double v = std::strtod(s.c_str() + p, &end);
    return end == s.c_str() + p ? fallback : v;
}

static uint64_t uint64_field(const std::string& s, const char* key, uint64_t fallback = 0) {
    const std::string pat = key_pattern(key);
    size_t p = s.find(pat);
    if (p == std::string::npos) return fallback;
    p += pat.size();
    while (p < s.size() && std::isspace(static_cast<unsigned char>(s[p]))) ++p;
    uint64_t value = 0;
    bool any = false;
    for (; p < s.size(); ++p) {
        unsigned char ch = static_cast<unsigned char>(s[p]);
        if (!std::isdigit(ch)) break;
        any = true;
        value = value * 10 + static_cast<uint64_t>(ch - static_cast<unsigned char>('0'));
    }
    return any ? value : fallback;
}

static bool bool_field(const std::string& s, const char* key, bool fallback = false) {
    const std::string pat = key_pattern(key);
    size_t p = s.find(pat);
    if (p == std::string::npos) return fallback;
    p += pat.size();
    if (s.compare(p, 4, "true") == 0) return true;
    if (s.compare(p, 5, "false") == 0) return false;
    return fallback;
}

static std::string string_field(const std::string& s, const char* key) {
    const std::string pat = key_pattern(key);
    size_t p = s.find(pat);
    if (p == std::string::npos) return "";
    p += pat.size();
    if (p >= s.size() || s[p] != '"') return "";
    ++p;
    std::string out;
    bool escape = false;
    for (; p < s.size(); ++p) {
        char c = s[p];
        if (escape) {
            out.push_back(c);
            escape = false;
        } else if (c == '\\') {
            escape = true;
        } else if (c == '"') {
            break;
        } else {
            out.push_back(c);
        }
    }
    return out;
}

static GoalFeatures parse_goal(const char* gf_json) {
    std::string s(gf_json ? gf_json : "");
    GoalFeatures g;
    g.splitDepth = static_cast<float>(number_field(s, "splitDepth"));
    g.assertedCount = static_cast<float>(number_field(s, "assertedCount"));
    g.ematchRounds = static_cast<float>(number_field(s, "ematchRounds"));
    g.splitTraceLen = static_cast<float>(number_field(s, "splitTraceLen"));
    g.numCandidates = static_cast<float>(number_field(s, "numCandidates", 1.0));
    return g;
}

static std::vector<Candidate> parse_candidates(const char* cands_json) {
    std::string s(cands_json ? cands_json : "");
    std::vector<Candidate> out;
    size_t p = 0;
    while (true) {
        size_t start = s.find('{', p);
        if (start == std::string::npos) break;
        size_t end = s.find('}', start + 1);
        if (end == std::string::npos) break;
        std::string obj = s.substr(start, end - start + 1);
        Candidate c;
        c.anchor = uint64_field(obj, "anchor");
        c.numCases = static_cast<int>(number_field(obj, "numCases"));
        c.isRec = bool_field(obj, "isRec");
        c.source = string_field(obj, "source");
        c.generation = static_cast<int>(number_field(obj, "generation"));
        c.tryPostpone = bool_field(obj, "tryPostpone");
        c.variant = string_field(obj, "variant");
        c.isGrindChoice = bool_field(obj, "isGrindChoice");
        if (c.anchor != 0) out.push_back(std::move(c));
        p = end + 1;
    }
    return out;
}

static int source_index(const std::string& source) {
    static const char* tags[] = {
        "ematch", "ext", "mbtc", "beta", "forallProp",
        "existsProp", "input", "inj", "guard"
    };
    for (int i = 0; i < 9; ++i) {
        if (source == tags[i]) return i;
    }
    return -1;
}

static int variant_index(const std::string& variant) {
    static const char* tags[] = { "default", "imp", "arg" };
    for (int i = 0; i < 3; ++i) {
        if (variant == tags[i]) return i;
    }
    return -1;
}

static int rank_in_unique_sorted(const std::vector<int>& sorted, int value) {
    auto it = std::lower_bound(sorted.begin(), sorted.end(), value);
    return static_cast<int>(it - sorted.begin());
}

static std::vector<int> unique_sorted(std::vector<int> xs) {
    std::sort(xs.begin(), xs.end());
    xs.erase(std::unique(xs.begin(), xs.end()), xs.end());
    return xs;
}

static std::vector<float> make_features(
    const Candidate& c,
    const GoalFeatures& g,
    const std::vector<Candidate>& cands,
    const std::vector<int>& sorted_cases,
    const std::vector<int>& sorted_gens,
    int min_cases,
    int min_gen,
    float input_source_fraction
) {
    std::vector<float> x(kInputDim, 0.0f);
    size_t i = 0;
    x[i++] = static_cast<float>(c.numCases);
    x[i++] = c.isRec ? 1.0f : 0.0f;
    int src = source_index(c.source);
    for (int j = 0; j < 9; ++j) x[i++] = (src == j) ? 1.0f : 0.0f;
    x[i++] = static_cast<float>(c.generation);
    x[i++] = g.splitDepth;
    x[i++] = g.assertedCount;
    x[i++] = g.ematchRounds;
    x[i++] = g.splitTraceLen;
    x[i++] = g.numCandidates;

    int same_cases = 0;
    for (const auto& other : cands) {
        if (other.numCases == c.numCases) ++same_cases;
    }
    const float n = static_cast<float>(std::max<size_t>(cands.size(), 1));

    x[i++] = static_cast<float>(rank_in_unique_sorted(sorted_cases, c.numCases));
    x[i++] = static_cast<float>(rank_in_unique_sorted(sorted_gens, c.generation));
    x[i++] = (c.numCases == min_cases) ? 1.0f : 0.0f;
    x[i++] = (c.generation == min_gen) ? 1.0f : 0.0f;
    x[i++] = n;
    x[i++] = static_cast<float>(same_cases) / n;
    x[i++] = input_source_fraction;

    // exp08 included three grindState count features.  SplitPolicy currently
    // sends an empty grindState, so these remain zero and match the Python
    // server's behavior.
    x[i++] = 0.0f;
    x[i++] = 0.0f;
    x[i++] = 0.0f;

    // new heuristics (exp09)
    x[i++] = c.tryPostpone ? 1.0f : 0.0f;
    int var = variant_index(c.variant);
    for (int j = 0; j < 3; ++j) x[i++] = (var == j) ? 1.0f : 0.0f;
    x[i++] = c.isGrindChoice ? 1.0f : 0.0f;

    return x;
}

static bool read_floats(std::ifstream& in, std::vector<float>& dst, size_t n) {
    dst.resize(n);
    in.read(reinterpret_cast<char*>(dst.data()), static_cast<std::streamsize>(n * sizeof(float)));
    return static_cast<size_t>(in.gcount()) == n * sizeof(float);
}

static bool load_weights_from(const char* path, Weights& w) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;

    char magic[8] = {};
    uint32_t version = 0, input_dim = 0, hidden_dim = 0;
    in.read(magic, sizeof(magic));
    in.read(reinterpret_cast<char*>(&version), sizeof(version));
    in.read(reinterpret_cast<char*>(&input_dim), sizeof(input_dim));
    in.read(reinterpret_cast<char*>(&hidden_dim), sizeof(hidden_dim));
    if (!in || std::strncmp(magic, "NGEXP09", 7) != 0 ||
        version != 1 || input_dim != kInputDim || hidden_dim == 0) {
        return false;
    }

    const size_t hidden = static_cast<size_t>(hidden_dim);
    if (!read_floats(in, w.fc1_w, hidden * kInputDim)) return false;
    if (!read_floats(in, w.fc1_b, hidden)) return false;
    if (!read_floats(in, w.fc2_w, hidden * hidden)) return false;
    if (!read_floats(in, w.fc2_b, hidden)) return false;
    if (!read_floats(in, w.fc3_w, hidden)) return false;
    in.read(reinterpret_cast<char*>(&w.fc3_b), sizeof(float));
    if (!in) return false;

    w.input_dim = input_dim;
    w.hidden_dim = hidden_dim;
    w.loaded = true;
    return true;
}

static bool ensure_weights() {
    if (g_load_attempted) return g_weights.loaded;
    g_load_attempted = true;

    std::vector<std::string> paths;
    if (const char* env = std::getenv("GRIND_NATIVE_WEIGHTS")) {
        if (*env) paths.emplace_back(env);
    }
    paths.emplace_back("../training/experiments/exp09_heuristics/model.native.bin");
    paths.emplace_back("training/experiments/exp09_heuristics/model.native.bin");
    paths.emplace_back("../training/experiments/exp08_num_pool_counts/model.native.bin");
    paths.emplace_back("training/experiments/exp08_num_pool_counts/model.native.bin");

    for (const auto& path : paths) {
        if (load_weights_from(path.c_str(), g_weights)) return true;
    }

    std::cerr << "[neural_grind] native exp08 weights not found; set GRIND_NATIVE_WEIGHTS\n";
    return false;
}

static float score_one(const Weights& w, const std::vector<float>& x) {
    const size_t hidden = static_cast<size_t>(w.hidden_dim);
    std::vector<float> h1(hidden);
    std::vector<float> h2(hidden);

    for (size_t j = 0; j < hidden; ++j) {
        float sum = w.fc1_b[j];
        const float* row = &w.fc1_w[j * kInputDim];
        for (uint32_t i = 0; i < kInputDim; ++i) sum += row[i] * x[i];
        h1[j] = std::max(sum, 0.0f);
    }

    for (size_t j = 0; j < hidden; ++j) {
        float sum = w.fc2_b[j];
        const float* row = &w.fc2_w[j * hidden];
        for (size_t i = 0; i < hidden; ++i) sum += row[i] * h1[i];
        h2[j] = std::max(sum, 0.0f);
    }

    float out = w.fc3_b;
    for (size_t i = 0; i < hidden; ++i) out += w.fc3_w[i] * h2[i];
    return out;
}

static std::string choose_exp08(const char* gf_json, const char* cands_json) {
    if (!ensure_weights()) return "0 0";

    GoalFeatures goal = parse_goal(gf_json);
    std::vector<Candidate> cands = parse_candidates(cands_json);
    if (cands.empty()) return "0 0";

    std::vector<int> cases;
    std::vector<int> gens;
    int input_sources = 0;
    for (const auto& c : cands) {
        cases.push_back(c.numCases);
        gens.push_back(c.generation);
        if (c.source == "input") ++input_sources;
    }
    std::vector<int> sorted_cases = unique_sorted(cases);
    std::vector<int> sorted_gens = unique_sorted(gens);
    int min_cases = *std::min_element(cases.begin(), cases.end());
    int min_gen = *std::min_element(gens.begin(), gens.end());
    float input_source_fraction =
        static_cast<float>(input_sources) / static_cast<float>(std::max<size_t>(cands.size(), 1));

    std::vector<Scored> scored;
    scored.reserve(cands.size());
    for (const auto& c : cands) {
        auto x = make_features(c, goal, cands, sorted_cases, sorted_gens,
                               min_cases, min_gen, input_source_fraction);
        scored.push_back({c.anchor, score_one(g_weights, x)});
    }

    std::sort(scored.begin(), scored.end(), [](const Scored& a, const Scored& b) {
        return a.score > b.score;
    });

    float margin = scored.size() >= 2 ? scored[0].score - scored[1].score : 1000000.0f;
    int margin_milli = static_cast<int>(std::max(0.0f, std::round(margin * 1000.0f)));

    std::ostringstream out;
    out << scored[0].anchor << " " << margin_milli;
    return out.str();
}

}  // namespace

#ifdef NEURAL_GRIND_STANDALONE

static std::string json_subvalue(const std::string& line, const char* key) {
    std::string pat = std::string("\"") + key + "\":";
    size_t p = line.find(pat);
    if (p == std::string::npos) return "";
    p += pat.size();
    while (p < line.size() && std::isspace(static_cast<unsigned char>(line[p]))) ++p;
    if (p >= line.size()) return "";
    char open = line[p];
    char close = open == '{' ? '}' : (open == '[' ? ']' : '\0');
    if (close == '\0') return "";
    int depth = 0;
    bool in_string = false;
    bool escape = false;
    for (size_t i = p; i < line.size(); ++i) {
        char c = line[i];
        if (escape) {
            escape = false;
            continue;
        }
        if (in_string) {
            if (c == '\\') escape = true;
            else if (c == '"') in_string = false;
            continue;
        }
        if (c == '"') {
            in_string = true;
        } else if (c == open) {
            ++depth;
        } else if (c == close) {
            --depth;
            if (depth == 0) return line.substr(p, i - p + 1);
        }
    }
    return "";
}

int main(int argc, char** argv) {
    for (int i = 1; i + 1 < argc; ++i) {
        if (std::string(argv[i]) == "--model") {
            setenv("GRIND_NATIVE_WEIGHTS", argv[i + 1], 1);
            ++i;
        }
    }

    std::string line;
    while (std::getline(std::cin, line)) {
        std::string goal = json_subvalue(line, "goalFeatures");
        std::string cands = json_subvalue(line, "candidates");
        if (goal.empty() || cands.empty()) {
            std::cout << "0 0" << std::endl;
            continue;
        }
        std::cout << choose_exp08(goal.c_str(), cands.c_str()) << std::endl;
    }
    return 0;
}

#else

extern "C" LEAN_EXPORT lean_obj_res lean_exp08_choose(
    b_lean_obj_arg gf_json,
    b_lean_obj_arg cands_json
) {
    const char* gf = lean_string_cstr(gf_json);
    const char* cands = lean_string_cstr(cands_json);
    std::string result = choose_exp08(gf, cands);
    return lean_mk_string(result.c_str());
}

extern "C" LEAN_EXPORT double lean_neural_score(
    b_lean_obj_arg goal_str,
    b_lean_obj_arg cand_str
) {
    (void)goal_str;
    (void)cand_str;
    return 0.0;
}

#endif
