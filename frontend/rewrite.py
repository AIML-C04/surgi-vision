import re

with open('src/pages/Analysis.jsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace the GET call
code = re.sub(
    r"const res = await axios\.get\(`\$\{API_URL\}/api/v1/analysis/\$\{id\}`,\s*config\);",
    """let res;
        try {
          res = await axios.get(`${API_URL}/api/v1/analysis/by-video/${id}`, config);
        } catch (err) {
          if (err.response?.status === 404) {
            if (isMounted) setAnalysis({ status: 'NOT_STARTED', video_id: id });
            return;
          }
          throw err;
        }""",
    code
)

# Replace detections GET call
code = re.sub(
    r"const detRes = await axios\.get\(`\$\{API_URL\}/api/v1/analysis/\$\{id\}/detections`,\s*config\);",
    r"const detRes = await axios.get(`${API_URL}/api/v1/analysis/${res.data.id}/detections`, config);",
    code
)

# Extract everything from fetchStatus() to the end of the first useEffect
part1 = code[:code.find("    const API_URL = import.meta.env.VITE_API_URL")]
part2 = code[code.find("    const API_URL = import.meta.env.VITE_API_URL"):]

# Replace socket creation area
new_part2 = part2.replace(
    "    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';",
    """  }, [id, token]);

  useEffect(() => {
    let isMounted = true;
    if (!analysis || !analysis.id || analysis.status === 'completed' || analysis.status === 'failed' || analysis.status === 'NOT_STARTED') return;
    
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';"""
)
new_part2 = new_part2.replace("ws/${id}", "ws/${analysis.id}")
new_part2 = new_part2.replace("}, [id, token]);", "}, [analysis?.id, analysis?.status, token]);", 1)

code = part1 + new_part2

with open('src/pages/Analysis.jsx', 'w', encoding='utf-8') as f:
    f.write(code)

