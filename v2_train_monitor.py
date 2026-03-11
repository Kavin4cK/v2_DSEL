#!/usr/bin/env python3
"""
Patent Figures Generator for Hot Axle Monitoring System
Generates all 4 figures as PNG images
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
import numpy as np

# Set style
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10

# Color scheme
IEEEBLUE = '#0066CC'
PHASE1 = '#FFC864'
PHASE2 = '#64C8FF'
PHASE3 = '#96FF96'
PHASE4 = '#FF96C8'

def create_interaction_flow():
    """Generate System Interaction Flow diagram"""
    fig, ax = plt.subplots(figsize=(8, 11))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis('off')
    
    # Title
    ax.text(5, 13.5, 'System Interaction Flow', 
            ha='center', fontsize=16, weight='bold', color=IEEEBLUE)
    
    # Start
    start = mpatches.Ellipse((5, 12.5), 1.5, 0.6, 
                             facecolor='#FF9999', edgecolor='black', linewidth=2)
    ax.add_patch(start)
    ax.text(5, 12.5, 'Power On', ha='center', va='center', weight='bold')
    
    y_pos = 11.8
    
    # Phase 1
    phase1 = FancyBboxPatch((3, y_pos-0.4), 4, 0.8, 
                            boxstyle="round,pad=0.1", 
                            facecolor=PHASE1, edgecolor='black', linewidth=2)
    ax.add_patch(phase1)
    ax.text(5, y_pos, 'PHASE 1\nPub/Sub Discovery', 
            ha='center', va='center', weight='bold', fontsize=9)
    
    y_pos -= 0.8
    detail1 = FancyBboxPatch((3.2, y_pos-0.35), 3.6, 0.7, 
                             facecolor='#CCE5FF', edgecolor='black', linewidth=1)
    ax.add_patch(detail1)
    ax.text(5, y_pos, 'Each coach broadcasts/\nlistens to IDs (5s)', 
            ha='center', va='center', fontsize=8)
    
    # Annotations
    ax.text(8, y_pos+0.4, 'Phase 1:\nAutonomous\nneighbor\ndetection', 
            fontsize=7, bbox=dict(boxstyle='round', facecolor='#EEEEEE'))
    
    y_pos -= 1.3
    
    # Phase 2
    phase2 = FancyBboxPatch((3, y_pos-0.4), 4, 0.8, 
                            boxstyle="round,pad=0.1", 
                            facecolor=PHASE2, edgecolor='black', linewidth=2)
    ax.add_patch(phase2)
    ax.text(5, y_pos, 'PHASE 2\n1-D Tensor Formation', 
            ha='center', va='center', weight='bold', fontsize=9)
    
    y_pos -= 0.8
    detail2 = FancyBboxPatch((3.2, y_pos-0.35), 3.6, 0.7, 
                             facecolor='#CCE5FF', edgecolor='black', linewidth=1)
    ax.add_patch(detail2)
    ax.text(5, y_pos, 'Store [prev, curr, next]\nin local memory', 
            ha='center', va='center', fontsize=8)
    
    ax.text(8, y_pos, 'Phase 2:\nLocal data\nstructure\ncreation', 
            fontsize=7, bbox=dict(boxstyle='round', facecolor='#EEEEEE'))
    
    y_pos -= 1.3
    
    # Phase 3
    phase3 = FancyBboxPatch((3, y_pos-0.4), 4, 0.8, 
                            boxstyle="round,pad=0.1", 
                            facecolor=PHASE3, edgecolor='black', linewidth=2)
    ax.add_patch(phase3)
    ax.text(5, y_pos, 'PHASE 3\nRaspberry Pi Discovery', 
            ha='center', va='center', weight='bold', fontsize=9)
    
    y_pos -= 0.8
    for i, text in enumerate(['Probe coaches 0-3', 
                              '2-D Tensor Aggregation\n(Stack all 1-D tensors)', 
                              'Linked List Reconstruction\n(Find head, traverse)']):
        detail = FancyBboxPatch((3.2, y_pos-0.35), 3.6, 0.6, 
                                facecolor='#CCE5FF', edgecolor='black', linewidth=1)
        ax.add_patch(detail)
        ax.text(5, y_pos, text, ha='center', va='center', fontsize=7)
        y_pos -= 0.75
    
    ax.text(8, y_pos+1.5, 'Phase 3:\nCentral\naggregation\nmapping', 
            fontsize=7, bbox=dict(boxstyle='round', facecolor='#EEEEEE'))
    
    y_pos -= 0.3
    
    # Phase 4
    phase4 = FancyBboxPatch((3, y_pos-0.4), 4, 0.8, 
                            boxstyle="round,pad=0.1", 
                            facecolor=PHASE4, edgecolor='black', linewidth=2)
    ax.add_patch(phase4)
    ax.text(5, y_pos, 'PHASE 4\nContinuous Monitoring', 
            ha='center', va='center', weight='bold', fontsize=9)
    
    y_pos -= 1.2
    
    # Monitoring loop
    loop_box = FancyBboxPatch((3.2, y_pos-2.2), 3.6, 2.4, 
                              facecolor='#FFFFCC', edgecolor='black', linewidth=2)
    ax.add_patch(loop_box)
    
    loop_items = ['Request TEMP from Ci', 'Receive temperature', 
                  'Update GUI display', 'Check thresholds', 'Generate alerts']
    for i, item in enumerate(loop_items):
        item_box = FancyBboxPatch((3.4, y_pos-0.35-i*0.45), 3.2, 0.4, 
                                  facecolor='white', edgecolor='black', linewidth=1)
        ax.add_patch(item_box)
        ax.text(5, y_pos-0.15-i*0.45, item, ha='center', va='center', fontsize=7)
    
    # Loop arrow
    ax.annotate('', xy=(3.4, y_pos-0.15), xytext=(3.4, y_pos-2.15),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    ax.annotate('', xy=(3.2, y_pos-2.15), xytext=(3.4, y_pos-2.15),
                arrowprops=dict(arrowstyle='-', lw=2, color='red'))
    ax.annotate('', xy=(3.2, y_pos-0.15), xytext=(3.2, y_pos-2.15),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    ax.text(2.5, y_pos-1, '1 Hz\nLoop', fontsize=6, color='red')
    
    ax.text(8, y_pos-1, 'Phase 4:\nReal-time\nmonitoring\nloop', 
            fontsize=7, bbox=dict(boxstyle='round', facecolor='#EEEEEE'))
    
    # Arrows between phases
    arrow_y = [12.2, 10.3, 8.6, 6.3, 4.5]
    for i in range(len(arrow_y)-1):
        ax.annotate('', xy=(5, arrow_y[i+1]+0.4), xytext=(5, arrow_y[i]-0.4),
                    arrowprops=dict(arrowstyle='->', lw=3, color='black'))
    
    plt.tight_layout()
    plt.savefig('figure_interaction_flow.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: figure_interaction_flow.png")
    plt.close()


def create_pubsub_discovery():
    """Generate Figure 1: Pub/Sub Neighbor Discovery"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(6, 7.5, 'Figure 1: Pub/Sub Neighbor Discovery', 
            ha='center', fontsize=16, weight='bold', color=IEEEBLUE)
    ax.text(6, 7, 'Setup Phase (first 5 seconds)', 
            ha='center', fontsize=12)
    
    # Coach boxes
    coaches = [
        {'x': 1.5, 'name': 'Coach C0', 'broadcast': 'D8=0, D7=0\n(ID = 0)', 
         'listen': 'Listen:\nD10/D11\n(Hears ID=1)'},
        {'x': 5.5, 'name': 'Coach C1', 'broadcast': 'D8=0, D7=1\n(ID = 1)', 
         'listen': 'Listen L/R:\nD4/D5, D10/D11\n(Hears 0, 2)'},
        {'x': 9.5, 'name': 'Coach C2', 'broadcast': 'D8=1, D7=0\n(ID = 2)', 
         'listen': 'Listen:\nD4/D5\n(Hears ID=1)'}
    ]
    
    for coach in coaches:
        box = FancyBboxPatch((coach['x']-1, 3.5), 2, 2.5, 
                             boxstyle="round,pad=0.05", 
                             facecolor='#CCE5FF', edgecolor='black', linewidth=2)
        ax.add_patch(box)
        ax.text(coach['x'], 5.7, coach['name'], 
                ha='center', va='top', weight='bold', fontsize=10)
        ax.text(coach['x'], 5.2, 'Broadcast:\n' + coach['broadcast'], 
                ha='center', va='top', fontsize=8)
        ax.text(coach['x'], 4, coach['listen'], 
                ha='center', va='top', fontsize=7)
    
    # Broadcast arrows (red)
    ax.annotate('', xy=(4.5, 5), xytext=(2.5, 5),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    ax.text(3.5, 5.3, 'Broadcast', ha='center', fontsize=7, color='red')
    
    ax.annotate('', xy=(8.5, 5), xytext=(6.5, 5),
                arrowprops=dict(arrowstyle='->', lw=2, color='red'))
    ax.text(7.5, 5.3, 'Broadcast', ha='center', fontsize=7, color='red')
    
    # Listen arrows (blue dashed)
    ax.annotate('', xy=(2.5, 4.5), xytext=(4.5, 4.5),
                arrowprops=dict(arrowstyle='->', lw=2, color='blue', linestyle='dashed'))
    ax.text(3.5, 4.2, 'Listen', ha='center', fontsize=7, color='blue')
    
    ax.annotate('', xy=(6.5, 4.5), xytext=(8.5, 4.5),
                arrowprops=dict(arrowstyle='->', lw=2, color='blue', linestyle='dashed'))
    ax.text(7.5, 4.2, 'Listen', ha='center', fontsize=7, color='blue')
    
    # Result box
    result = FancyBboxPatch((2, 0.5), 8, 1.8, 
                            facecolor='#FFFFCC', edgecolor='black', linewidth=2)
    ax.add_patch(result)
    ax.text(6, 2, 'Result - 1-D Tensors Formed:', 
            ha='center', va='top', weight='bold', fontsize=10)
    ax.text(6, 1.5, 'C0: left=-1, right=1 → [-1, 0, 1]\n'
                    'C1: left=0, right=2 → [0, 1, 2]\n'
                    'C2: left=1, right=-1 → [1, 2, -1]', 
            ha='center', va='top', fontsize=9, family='monospace')
    
    # Legend
    legend_box = FancyBboxPatch((10.5, 5.5), 1.3, 1.2, 
                                facecolor='white', edgecolor='black', linewidth=1)
    ax.add_patch(legend_box)
    ax.text(11.15, 6.5, 'Legend:', ha='center', weight='bold', fontsize=8)
    ax.plot([10.7, 11], [6.2, 6.2], 'r-', lw=2)
    ax.text(11.5, 6.2, 'Broadcast', ha='left', va='center', fontsize=7)
    ax.plot([10.7, 11], [5.8, 5.8], 'b--', lw=2)
    ax.text(11.5, 5.8, 'Listen', ha='left', va='center', fontsize=7)
    
    plt.tight_layout()
    plt.savefig('figure1_pubsub_discovery.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: figure1_pubsub_discovery.png")
    plt.close()


def create_2d_tensor():
    """Generate Figure 2: 2-D Tensor Formation"""
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.axis('off')
    
    # Title
    ax.text(6, 8.5, 'Figure 2: 2-D Tensor Formation', 
            ha='center', fontsize=16, weight='bold', color=IEEEBLUE)
    
    # Individual 1-D Tensors (Left)
    ax.text(2, 7.5, 'Individual 1-D Tensors', 
            ha='center', fontsize=12, weight='bold')
    
    colors = ['#FFCCCC', '#CCFFCC', '#CCCCFF']
    tensor_data = [
        {'label': 'C0:', 'values': ['-1', '0', '1'], 'y': 6.5},
        {'label': 'C1:', 'values': ['0', '1', '2'], 'y': 5.5},
        {'label': 'C2:', 'values': ['1', '2', '-1'], 'y': 4.5}
    ]
    
    for tensor in tensor_data:
        ax.text(0.3, tensor['y'], tensor['label'], 
                ha='right', va='center', fontsize=10)
        for i, (val, color) in enumerate(zip(tensor['values'], colors)):
            box = Rectangle((0.8 + i*0.8, tensor['y']-0.3), 0.7, 0.6, 
                           facecolor=color, edgecolor='black', linewidth=1.5)
            ax.add_patch(box)
            ax.text(0.8 + i*0.8 + 0.35, tensor['y'], val, 
                   ha='center', va='center', fontsize=11, weight='bold')
    
    # Arrow
    ax.annotate('Stack', xy=(5.5, 5.5), xytext=(4, 5.5),
                arrowprops=dict(arrowstyle='->', lw=3, color='blue'),
                fontsize=12, weight='bold', ha='center')
    
    # 2-D Tensor (Right)
    ax.text(8.5, 7.5, '2-D Tensor (Matrix)', 
            ha='center', fontsize=12, weight='bold')
    
    # Matrix brackets
    ax.plot([6.3, 6.3], [7, 4], 'k-', lw=3)
    ax.plot([6.3, 6.5], [7, 7], 'k-', lw=3)
    ax.plot([6.3, 6.5], [4, 4], 'k-', lw=3)
    
    ax.plot([10.7, 10.7], [7, 4], 'k-', lw=3)
    ax.plot([10.5, 10.7], [7, 7], 'k-', lw=3)
    ax.plot([10.5, 10.7], [4, 4], 'k-', lw=3)
    
    # Matrix content
    matrix_values = [
        ['-1', '0', '1'],
        ['0', '1', '2'],
        ['1', '2', '-1']
    ]
    
    for i, row in enumerate(matrix_values):
        ax.text(5.8, 6.5-i, f'Row {i}', ha='right', va='center', fontsize=8)
        for j, (val, color) in enumerate(zip(row, colors)):
            box = Rectangle((6.8 + j*1.2, 6.2-i-0.3), 1.0, 0.6, 
                           facecolor=color, edgecolor='black', linewidth=1.5)
            ax.add_patch(box)
            ax.text(6.8 + j*1.2 + 0.5, 6.2-i, val, 
                   ha='center', va='center', fontsize=11, weight='bold')
    
    # Column labels
    labels = ['Previous', 'Current', 'Next']
    label_colors = ['#CC0000', '#00CC00', '#0000CC']
    for i, (label, color) in enumerate(zip(labels, label_colors)):
        ax.text(6.8 + i*1.2 + 0.5, 3.5, label, 
               ha='center', fontsize=9, color=color, weight='bold')
    
    # Explanation
    explanation = FancyBboxPatch((1.5, 0.5), 9, 2, 
                                 facecolor='#FFFFCC', edgecolor='black', linewidth=2)
    ax.add_patch(explanation)
    ax.text(6, 2.2, 'Tensor Structure:', 
            ha='center', va='top', weight='bold', fontsize=11)
    ax.text(6, 1.7, '• Each row = one coach\'s topological position\n'
                    '• Columns = [previous_id, current_id, next_id]\n'
                    '• -1 represents NULL (no neighbor)', 
            ha='center', va='top', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('figure2_2d_tensor.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: figure2_2d_tensor.png")
    plt.close()


def create_linked_list():
    """Generate Figure 3: Linked List Reconstruction"""
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(6.5, 9.5, 'Figure 3: Linked List Reconstruction', 
            ha='center', fontsize=16, weight='bold', color=IEEEBLUE)
    
    # Step 1
    step1_box = FancyBboxPatch((0.5, 7.5), 5, 1.2, 
                               facecolor='#FFFFCC', edgecolor='black', linewidth=1.5)
    ax.add_patch(step1_box)
    ax.text(3, 8.5, 'Step 1: Find HEAD', 
            ha='center', va='top', weight='bold', fontsize=11)
    ax.text(3, 8.1, 'Search 2-D tensor for row with left=-1\n'
                    'Row 0: [-1, 0, 1] → C0 is HEAD', 
            ha='center', va='top', fontsize=9)
    
    # Step 2
    step2_box = FancyBboxPatch((0.5, 6), 5, 1.2, 
                               facecolor='#FFFFCC', edgecolor='black', linewidth=1.5)
    ax.add_patch(step2_box)
    ax.text(3, 7, 'Step 2: Traverse', 
            ha='center', va='top', weight='bold', fontsize=11)
    ax.text(3, 6.6, 'HEAD → C0 (next=1)\n'
                    '→ C1 (next=2)\n'
                    '→ C2 (next=-1) → NULL', 
            ha='center', va='top', fontsize=9)
    
    # Step 3
    ax.text(6.5, 5.5, 'Step 3: Visual Linked List', 
            ha='center', fontsize=12, weight='bold')
    
    # HEAD pointer
    ax.text(0.8, 4, 'HEAD', ha='center', va='center', 
            fontsize=12, weight='bold', color='red')
    ax.annotate('', xy=(1.8, 4), xytext=(1.3, 4),
                arrowprops=dict(arrowstyle='->', lw=3, color='red'))
    
    # Coach nodes
    coaches = [
        {'x': 3, 'id': 'C0', 'left': '← -1', 'right': '1 →', 'temp': '25.3°C'},
        {'x': 6.5, 'id': 'C1', 'left': '← 0', 'right': '2 →', 'temp': '28.7°C'},
        {'x': 10, 'id': 'C2', 'left': '← 1', 'right': '-1 →', 'temp': '30.1°C'}
    ]
    
    for coach in coaches:
        # Node box (3 parts)
        box = FancyBboxPatch((coach['x']-1, 3), 2, 2, 
                            facecolor='#CCE5FF', edgecolor='black', linewidth=2)
        ax.add_patch(box)
        
        # Dividers
        ax.plot([coach['x']-1, coach['x']+1], [4.3, 4.3], 'k-', lw=1)
        ax.plot([coach['x']-1, coach['x']+1], [3.7, 3.7], 'k-', lw=1)
        
        ax.text(coach['x'], 4.65, coach['left'], 
               ha='center', va='center', fontsize=8)
        ax.text(coach['x'], 4, coach['id'], 
               ha='center', va='center', fontsize=12, weight='bold')
        ax.text(coach['x'], 3.35, coach['right'], 
               ha='center', va='center', fontsize=8)
        ax.text(coach['x'], 2.7, coach['temp'], 
               ha='center', va='top', fontsize=9)
    
    # Next arrows
    ax.annotate('', xy=(5.5, 4), xytext=(4, 4),
                arrowprops=dict(arrowstyle='->', lw=3, color='green'))
    ax.text(4.75, 4.3, 'next', ha='center', fontsize=8)
    
    ax.annotate('', xy=(9, 4), xytext=(7.5, 4),
                arrowprops=dict(arrowstyle='->', lw=3, color='green'))
    ax.text(8.25, 4.3, 'next', ha='center', fontsize=8)
    
    # NULL
    ax.text(11.5, 4, 'NULL', ha='center', va='center', 
            fontsize=12, weight='bold', color='gray')
    
    # Properties box
    props_box = FancyBboxPatch((1.5, 0.3), 10, 1.5, 
                               facecolor='#CCFFCC', edgecolor='black', linewidth=2)
    ax.add_patch(props_box)
    ax.text(6.5, 1.6, 'Linked List Properties:', 
            ha='center', va='top', weight='bold', fontsize=11)
    ax.text(6.5, 1.2, '• Doubly linked: Each node knows previous and next\n'
                      '• Traversable: Can navigate from HEAD to tail\n'
                      '• Dynamic: Can be rebuilt when coaches change', 
            ha='center', va='top', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('figure3_linked_list.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: figure3_linked_list.png")
    plt.close()


def create_self_reconfiguration():
    """Generate Figure 4: Self-Reconfiguration Example"""
    fig, ax = plt.subplots(figsize=(11, 10))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 12)
    ax.axis('off')
    
    # Title
    ax.text(6, 11.5, 'Figure 4: Self-Reconfiguration Example', 
            ha='center', fontsize=16, weight='bold', color=IEEEBLUE)
    
    # Initial configuration
    ax.text(1, 10.5, 'Initial: 3 Coaches', 
            ha='left', fontsize=11, weight='bold')
    
    for i, name in enumerate(['C0', 'C1', 'C2']):
        box = FancyBboxPatch((1.5+i*1.5, 9.5), 1.2, 0.8, 
                            facecolor='#CCE5FF', edgecolor='black', linewidth=2)
        ax.add_patch(box)
        ax.text(2.1+i*1.5, 9.9, name, ha='center', va='center', 
               fontsize=10, weight='bold')
        if i < 2:
            ax.annotate('', xy=(2.7+(i+1)*1.5, 9.9), xytext=(2.7+i*1.5, 9.9),
                       arrowprops=dict(arrowstyle='->', lw=2, color='black'))
    
    # New configuration
    ax.text(1, 8.5, 'New: C3 Inserted', 
            ha='left', fontsize=11, weight='bold')
    
    coaches_new = ['C0', 'C1', 'C3', 'C2']
    for i, name in enumerate(coaches_new):
        color = '#FFFFAA' if name == 'C3' else '#CCE5FF'
        lw = 3 if name == 'C3' else 2
        box = FancyBboxPatch((1+i*1.2, 7.5), 1, 0.8, 
                            facecolor=color, edgecolor='black', linewidth=lw)
        ax.add_patch(box)
        ax.text(1.5+i*1.2, 7.9, name, ha='center', va='center', 
               fontsize=10, weight='bold')
        if i < 3:
            ax.annotate('', xy=(2+(i+1)*1.2, 7.9), xytext=(2+i*1.2, 7.9),
                       arrowprops=dict(arrowstyle='->', lw=2, color='black'))
    
    ax.text(2.5, 7, 'NEW', ha='center', fontsize=8, color='red', weight='bold')
    
    # Pub/Sub box
    pubsub_box = FancyBboxPatch((6.5, 9), 5, 1.8, 
                                facecolor='#FFDDAA', edgecolor='black', linewidth=1.5)
    ax.add_patch(pubsub_box)
    ax.text(9, 10.6, 'Pub/Sub Re-Executes:', 
            ha='center', va='top', weight='bold', fontsize=10)
    ax.text(9, 10.2, 'C1 hears C3 on right\n'
                     'C3 hears C1 left, C2 right\n'
                     'C2 hears C3 on left', 
            ha='center', va='top', fontsize=8)
    
    # Old 1-D Tensors
    ax.text(2, 6.3, 'Old 1-D Tensors', ha='center', fontsize=10, weight='bold')
    
    old_tensors = [
        ['C0:', ['-1', '0', '1'], 5.8, ['#DDDDDD', '#DDDDDD', '#DDDDDD']],
        ['C1:', ['0', '1', '2'], 5.2, ['#FFCCCC', '#DDDDDD', '#FFCCCC']],
        ['C2:', ['1', '2', '-1'], 4.6, ['#FFCCCC', '#DDDDDD', '#DDDDDD']]
    ]
    
    for label, values, y, colors in old_tensors:
        ax.text(0.3, y, label, ha='right', va='center', fontsize=8)
        for i, (val, color) in enumerate(zip(values, colors)):
            box = Rectangle((0.6 + i*0.6, y-0.2), 0.55, 0.4, 
                           facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(box)
            ax.text(0.6 + i*0.6 + 0.275, y, val, 
                   ha='center', va='center', fontsize=8)
    
    # New 1-D Tensors
    ax.text(5.5, 6.3, 'New 1-D Tensors', ha='center', fontsize=10, weight='bold')
    
    new_tensors = [
        ['C0:', ['-1', '0', '1'], 5.8, ['#DDDDDD', '#DDDDDD', '#DDDDDD'], ''],
        ['C1:', ['0', '1', '3'], 5.2, ['#CCFFCC', '#DDDDDD', '#CCFFCC'], 'updated'],
        ['C3:', ['1', '3', '2'], 4.6, ['#FFFFAA', '#FFFFAA', '#FFFFAA'], 'NEW'],
        ['C2:', ['3', '2', '-1'], 4.0, ['#CCFFCC', '#DDDDDD', '#DDDDDD'], 'updated']
    ]
    
    for label, values, y, colors, status in new_tensors:
        ax.text(3.8, y, label, ha='right', va='center', fontsize=8)
        for i, (val, color) in enumerate(zip(values, colors)):
            box = Rectangle((4.1 + i*0.6, y-0.2), 0.55, 0.4, 
                           facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(box)
            ax.text(4.1 + i*0.6 + 0.275, y, val, 
                   ha='center', va='center', fontsize=8)
        if status:
            color = 'orange' if status == 'NEW' else 'green'
            ax.text(5.9, y, status, ha='left', va='center', 
                   fontsize=7, color=color, weight='bold')
    
    # Old 2-D Tensor
    ax.text(2, 3.2, 'Old 2-D Tensor', ha='center', fontsize=10, weight='bold')
    
    old_matrix = [['-1', '0', '1'], ['0', '1', '2'], ['1', '2', '-1']]
    for i, row in enumerate(old_matrix):
        for j, val in enumerate(row):
            box = Rectangle((0.8 + j*0.6, 2.4-i*0.5), 0.55, 0.45, 
                           facecolor='#DDDDDD', edgecolor='black', linewidth=1)
            ax.add_patch(box)
            ax.text(0.8 + j*0.6 + 0.275, 2.625-i*0.5, val, 
                   ha='center', va='center', fontsize=8)
    
    # Arrow
    ax.annotate('', xy=(4, 2.4), xytext=(3.2, 2.4),
                arrowprops=dict(arrowstyle='->', lw=3, color='blue'))
    
    # New 2-D Tensor
    ax.text(6.5, 3.2, 'New 2-D Tensor', ha='center', fontsize=10, weight='bold')
    
    new_matrix = [
        [['-1', '0', '1'], ['#DDDDDD', '#DDDDDD', '#DDDDDD']],
        [['0', '1', '3'], ['#CCFFCC', '#DDDDDD', '#CCFFCC']],
        [['1', '3', '2'], ['#FFFFAA', '#FFFFAA', '#FFFFAA']],
        [['3', '2', '-1'], ['#CCFFCC', '#DDDDDD', '#DDDDDD']]
    ]
    
    for i, (row, colors) in enumerate(new_matrix):
        for j, (val, color) in enumerate(zip(row, colors)):
            box = Rectangle((5.2 + j*0.6, 2.6-i*0.5), 0.55, 0.45, 
                           facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(box)
            ax.text(5.2 + j*0.6 + 0.275, 2.825-i*0.5, val, 
                   ha='center', va='center', fontsize=8)
    
    # Final message
    result_box = FancyBboxPatch((1, 0.2), 10, 0.9, 
                                facecolor='#CCFFCC', edgecolor='black', linewidth=3)
    ax.add_patch(result_box)
    ax.text(6, 0.85, 'Linked List Auto-Rebuilds: C0 → C1 → C3 → C2', 
            ha='center', va='top', fontsize=11, weight='bold')
    ax.text(6, 0.45, 'NO MANUAL RECONFIGURATION REQUIRED!', 
            ha='center', va='center', fontsize=11, color='red', weight='bold')
    
    plt.tight_layout()
    plt.savefig('figure4_self_reconfiguration.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: figure4_self_reconfiguration.png")
    plt.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Patent Figures Generator")
    print("="*60 + "\n")
    
    print("Generating figures...")
    print()
    
    create_interaction_flow()
    create_pubsub_discovery()
    create_2d_tensor()
    create_linked_list()
    create_self_reconfiguration()
    
    print()
    print("="*60)
    print("✅ All figures generated successfully!")
    print("="*60)
    print("\nGenerated files:")
    print("  • figure_interaction_flow.png")
    print("  • figure1_pubsub_discovery.png")
    print("  • figure2_2d_tensor.png")
    print("  • figure3_linked_list.png")
    print("  • figure4_self_reconfiguration.png")
    print("\nAll images saved at 300 DPI for high quality printing.")
    print()