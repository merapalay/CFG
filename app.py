import streamlit as st
import networkx as nx
import graphviz
import re

# --- Part 1: Universal CFG Builder ---

class UniversalCFGBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_counter = 0
        self.lines = []
        self.cursor = 0
        self.mode = "c_style" 

    def new_node(self, label, shape='box', style='filled', fillcolor='white'):
        self.node_counter += 1
        node_id = f"N{self.node_counter}"
        
        # Clean label for display
        clean = label.strip().replace('"', "'")
        if len(clean) > 40: clean = clean[:20] + "..." + clean[-15:]
        
        self.graph.add_node(node_id, label=clean, shape=shape, style=style, fillcolor=fillcolor)
        return node_id

    def connect(self, u, v, label=None):
        if u and v:
            self.graph.add_edge(u, v, label=label)

    def parse(self, code_text):
        # 1. Detect Mode & Normalize
        if "{" in code_text and "}" in code_text:
            self.mode = "c_style"
            code_text = re.sub(r'//.*', '', code_text)
            code_text = code_text.replace('{', '\n{\n').replace('}', '\n}\n').replace(';', ';\n')
            code_text = code_text.replace('else if', 'elif') 
        else:
            self.mode = "python_style"
            code_text = re.sub(r'#.*', '', code_text)
        
        self.lines = [line.strip() for line in code_text.split('\n') if line.strip()]
        self.cursor = 0
        
        start_node = self.new_node("START", shape='oval', fillcolor='#C8E6C9')
        last_node = self.parse_block(start_node)
        
        end_node = self.new_node("END", shape='oval', fillcolor='#FFCDD2')
        self.connect(last_node, end_node)
        
        return self.graph

    def parse_block(self, entry_node):
        current_node = entry_node
        buffer = []

        def flush_buffer():
            nonlocal current_node, buffer
            if buffer:
                label = "\n".join(buffer)
                block = self.new_node(label, shape='box')
                self.connect(current_node, block)
                current_node = block
                buffer = []

        while self.cursor < len(self.lines):
            line = self.lines[self.cursor]
            
            # --- 1. CRITICAL FIX: STOP BLOCK ON ELIF/ELSE ---
            # If we see 'elif' or 'else', the current block MUST end immediately.
            # We do NOT consume the line (cursor not incremented).
            # We return so the parent (the 'If' logic) can handle the branching.
            if line.startswith('elif') or line.startswith('else'):
                flush_buffer()
                return current_node

            # --- 2. Block Ends (C-style) ---
            if self.mode == 'c_style' and line == '}':
                flush_buffer()
                self.cursor += 1
                return current_node
            
            # --- 3. Skip Block Start (C-style) ---
            if self.mode == 'c_style' and line == '{':
                self.cursor += 1
                continue

            # --- 4. LOOPS (For/While) ---
            if line.startswith('for') or line.startswith('while'):
                flush_buffer()
                loop_cond = self.new_node(line, shape='diamond', fillcolor='#FFF9C4')
                self.connect(current_node, loop_cond)
                self.cursor += 1
                
                body_end = self.parse_block(loop_cond)
                self.connect(body_end, loop_cond, label="Loop")
                
                exit_node = self.new_node("Exit Loop", shape='point')
                self.connect(loop_cond, exit_node, label="False")
                current_node = exit_node

            # --- 5. IF / ELIF / ELSE ---
            elif line.startswith('if'):
                flush_buffer()
                exit_points = []
                
                # A. Main IF
                cond_node = self.new_node(line, shape='diamond', fillcolor='#FFE0B2')
                self.connect(current_node, cond_node)
                self.cursor += 1
                
                # Parse True Branch
                true_end = self.parse_block(cond_node)
                exit_points.append(true_end)
                
                last_decision = cond_node
                
                # B. Handle ELIF / ELSE
                # Because parse_block() now returns when it sees elif/else, 
                # we will be back here with the cursor pointing AT that line.
                while self.cursor < len(self.lines):
                    next_line = self.lines[self.cursor]
                    
                    if next_line.startswith('elif') or next_line.startswith('else if'):
                        self.cursor += 1
                        elif_node = self.new_node(next_line, shape='diamond', fillcolor='#FFE0B2')
                        self.connect(last_decision, elif_node, label="False")
                        
                        elif_end = self.parse_block(elif_node)
                        exit_points.append(elif_end)
                        last_decision = elif_node
                        
                    elif next_line.startswith('else'):
                        self.cursor += 1
                        else_start = self.new_node("Else", shape='point')
                        self.connect(last_decision, else_start, label="False")
                        
                        else_end = self.parse_block(else_start)
                        exit_points.append(else_end)
                        last_decision = None 
                        break
                    else:
                        break # Not an else/elif, just normal code following the if block
                
                # C. Merge
                merge_node = self.new_node("Merge", shape='point')
                for p in exit_points:
                    self.connect(p, merge_node)
                
                if last_decision:
                    self.connect(last_decision, merge_node, label="False")
                
                current_node = merge_node

            # --- 6. RETURN ---
            elif line.startswith('return'):
                flush_buffer()
                ret_node = self.new_node(line, shape='box', fillcolor='#FFCDD2')
                self.connect(current_node, ret_node)
                self.cursor += 1
                return ret_node
            
            # --- 7. NORMAL STATEMENTS ---
            else:
                buffer.append(line)
                self.cursor += 1
        
        flush_buffer()
        return current_node

# --- Part 2: Metrics (Same as before) ---

def calculate_metrics(G):
    if not G: return {}
    n = G.number_of_nodes()
    e = G.number_of_edges()
    p = len([n for n in G.nodes() if G.out_degree(n) > 1])
    cc = e - n + 2
    return { "Nodes": n, "Edges": e, "Complexity": cc, "Predicates": p, "Regions": cc }

# --- Part 3: UI ---

def main():
    st.set_page_config(layout="wide", page_title="Universal CFG")
    st.title("🔀 Universal CFG Generator")
    st.markdown("Supports **Python (elif)** and **C/Java (else if)** correctly.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Input Code")
        default_py = """x = 10
if x > 100:
    print("Huge")
elif x > 50:
    print("Big")
elif x > 10:
    print("Medium")
else:
    print("Small")

print("Done")"""
        code_input = st.text_area("Code Editor", value=default_py, height=500)

    with col2:
        st.subheader("Visualization")
        if code_input.strip():
            builder = UniversalCFGBuilder()
            try:
                G = builder.parse(code_input)
                metrics = calculate_metrics(G)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Nodes", metrics['Nodes'])
                c2.metric("Edges", metrics['Edges'])
                c3.metric("Complexity", metrics['Complexity'])
                c4.metric("Predicates", metrics['Predicates'])
                
                st.divider()
                
                dot = graphviz.Digraph()
                dot.attr(rankdir='TB')
                for n in G.nodes():
                    attrs = G.nodes[n]
                    dot.node(n, label=attrs.get('label',''), shape=attrs.get('shape','box'), style='filled', fillcolor=attrs.get('fillcolor','white'))
                for u, v in G.edges():
                    dot.edge(u, v, label=G.edges[u, v].get('label',''))
                st.graphviz_chart(dot)
            except Exception as e:
                st.error(f"Error: {e}")

if __name__ == "__main__":
    main()