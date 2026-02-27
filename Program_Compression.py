import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import heapq
import pickle
import os
import time
import threading

# ==========================================================
# ======================= LZW ==========================
# ==========================================================

MAX_DICT_SIZE = 4096

def lzw_compress(data, progress_callback=None):
    dict_size = 256
    dictionary = {bytes([i]): i for i in range(dict_size)}
    w = b""
    result = []

    total = len(data)

    for i, c in enumerate(data):
        wc = w + bytes([c])

        if wc in dictionary:
            w = wc
        else:
            if w:
                result.append(dictionary[w])

            if dict_size < MAX_DICT_SIZE:
                dictionary[wc] = dict_size
                dict_size += 1
            else:
                dictionary = {bytes([i]): i for i in range(256)}
                dict_size = 256

            w = bytes([c])

        if progress_callback and i % 10000 == 0:
            progress_callback(i / total * 50)

    if w:
        result.append(dictionary[w])

    return result


def lzw_decompress(compressed, progress_callback=None):
    dict_size = 256
    dictionary = {i: bytes([i]) for i in range(dict_size)}

    w = bytes([compressed.pop(0)])
    result = bytearray(w)

    total = len(compressed)

    for i, k in enumerate(compressed):
        if k in dictionary:
            entry = dictionary[k]
        elif k == dict_size:
            entry = w + bytes([w[0]])
        else:
            raise ValueError("Erreur LZW")

        result.extend(entry)

        if dict_size < MAX_DICT_SIZE:
            dictionary[dict_size] = w + bytes([entry[0]])
            dict_size += 1

        w = entry

        if progress_callback and i % 5000 == 0:
            progress_callback(50 + (i / total * 50))

    return bytes(result)

# ==========================================================
# ======================= HUFFMAN ==========================
# ==========================================================

class Node:
    def __init__(self, value=None, freq=None):
        self.value = value
        self.freq = freq
        self.left = None
        self.right = None

    def __lt__(self, other):
        return self.freq < other.freq


def huffman_compress(data):
    freq = {}
    for symbol in data:
        freq[symbol] = freq.get(symbol, 0) + 1

    heap = [Node(value=s, freq=f) for s, f in freq.items()]
    heapq.heapify(heap)

    while len(heap) > 1:
        n1 = heapq.heappop(heap)
        n2 = heapq.heappop(heap)
        merged = Node(freq=n1.freq + n2.freq)
        merged.left = n1
        merged.right = n2
        heapq.heappush(heap, merged)

    tree = heap[0]

    codes = {}
    def build(node, prefix=""):
        if node.value is not None:
            codes[node.value] = prefix or "0"
            return
        build(node.left, prefix + "0")
        build(node.right, prefix + "1")

    build(tree)

    bit_string = "".join(codes[s] for s in data)

    padding = (8 - len(bit_string) % 8) % 8
    bit_string += "0" * padding

    byte_array = bytearray(
        int(bit_string[i:i+8], 2)
        for i in range(0, len(bit_string), 8)
    )

    return byte_array, tree, padding


def huffman_decompress(data, tree, padding):
    bit_string = "".join(f"{byte:08b}" for byte in data)
    if padding:
        bit_string = bit_string[:-padding]

    decoded = []
    node = tree

    for bit in bit_string:
        node = node.left if bit == "0" else node.right
        if node.value is not None:
            decoded.append(node.value)
            node = tree

    return decoded

# ==========================================================
# ======================= GUI ==============================
# ==========================================================

selected_file = None

def choose_file():
    global selected_file
    selected_file = filedialog.askopenfilename()
    if selected_file:
        label_file.config(text=selected_file)

# ---------------- COMPRESSION ----------------

def compress_thread():
    start_time = time.time()

    save_path = filedialog.asksaveasfilename(
        defaultextension=".compr",
        filetypes=[("Compressed Files", "*.compr")]
    )
    if not save_path:
        return

    with open(selected_file, "rb") as f:
        data = f.read()

    original_size = len(data)

    def update_progress(value):
        progress["value"] = value
        elapsed = time.time() - start_time
        root.update_idletasks()
        label_status.config(
            text=f"Compression : {value:.1f}% | Temps : {elapsed:.1f}s"
        )

    lzw_data = lzw_compress(data, update_progress)
    huff_data, tree, padding = huffman_compress(lzw_data)

    with open(save_path, "wb") as f:
        pickle.dump((huff_data, tree, padding), f)

    compressed_size = os.path.getsize(save_path)
    ratio = (1 - compressed_size / original_size) * 100
    elapsed = time.time() - start_time

    progress["value"] = 100
    label_status.config(
        text=f"Compression terminée | Gain : {ratio:.2f}% | Temps : {elapsed:.2f}s"
    )

def compress_file():
    if not selected_file:
        messagebox.showerror("Erreur", "Choisissez un fichier.")
        return
    threading.Thread(target=compress_thread).start()

# ---------------- DECOMPRESSION ----------------

def decompress_thread():
    start_time = time.time()

    file_path = filedialog.askopenfilename(
        filetypes=[("Compressed Files", "*.compr")]
    )
    if not file_path:
        return

    save_path = filedialog.asksaveasfilename(
        defaultextension=".decompr",
        filetypes=[("Decompressed Files", "*.decompr")]
    )
    if not save_path:
        return

    with open(file_path, "rb") as f:
        huff_data, tree, padding = pickle.load(f)

    lzw_data = huffman_decompress(huff_data, tree, padding)

    def update_progress(value):
        progress["value"] = value
        elapsed = time.time() - start_time
        root.update_idletasks()
        label_status.config(
            text=f"Décompression : {value:.1f}% | Temps : {elapsed:.1f}s"
        )

    original_data = lzw_decompress(lzw_data, update_progress)

    with open(save_path, "wb") as f:
        f.write(original_data)

    elapsed = time.time() - start_time
    progress["value"] = 100
    label_status.config(
        text=f"Décompression terminée | Temps : {elapsed:.2f}s"
    )

def decompress_file():
    threading.Thread(target=decompress_thread).start()

# ==========================================================

root = tk.Tk()
root.title("Compresseur LZW + Huffman PRO")
root.geometry("650x420")
root.resizable(False, False)

title = tk.Label(root, text="Compression Sans Perte - LZW + Huffman",
                 font=("Arial", 16, "bold"))
title.pack(pady=10)

btn_choose = tk.Button(root, text="Choisir un fichier", command=choose_file)
btn_choose.pack(pady=5)

label_file = tk.Label(root, text="Aucun fichier sélectionné", wraplength=600)
label_file.pack(pady=5)

btn_compress = tk.Button(root, text="Compresser", command=compress_file)
btn_compress.pack(pady=10)

btn_decompress = tk.Button(root, text="Décompresser", command=decompress_file)
btn_decompress.pack(pady=5)

progress = ttk.Progressbar(root, length=550, mode="determinate")
progress.pack(pady=15)

label_status = tk.Label(root, text="En attente...")
label_status.pack(pady=5)

root.mainloop()