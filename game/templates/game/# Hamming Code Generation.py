# Hamming Code Generation

data = []

print("Enter 4 bits one by one:")

data.append(int(input("Bit 1: ")))
data.append(int(input("Bit 2: ")))
data.append(int(input("Bit 3: ")))
data.append(int(input("Bit 4: ")))

# Creating array for 7 bits
hamming = [0] * 7

# Put data bits
hamming[0] = data[0]
hamming[1] = data[1]
hamming[2] = data[2]
hamming[4] = data[3]

# Calculate parity bits (Even parity)
hamming[6] = hamming[0] ^ hamming[2] ^ hamming[4]
hamming[5] = hamming[0] ^ hamming[1] ^ hamming[4]
hamming[3] = hamming[0] ^ hamming[1] ^ hamming[2]

print("\nGenerated Hamming Code is:")
for bit in hamming:
    print(bit, end=" ")