import fitz

doc = fitz.open()

# Generate a PDF with Instruction, Questions, and continuation layout
page1 = doc.new_page(width=600, height=800)

y = 50

# Instruction (should be parsed out and ignored from questions)
page1.insert_text((50, y), "Instructions: Read the following passage carefully.", fontsize=12)
y += 30
page1.insert_text((50, y), "Section A: Multiple Choice", fontsize=14)
y += 40

# Question 1 (Normal Q)
page1.insert_text((50, y), "1. What is the value of acceleration due to gravity on Earth?", fontsize=12)
y += 20
page1.insert_text((60, y), "Assume ideal conditions and negligible air resistance.", fontsize=12) # continuation
y += 30

# Options for Q1 (Should break paragraph and be weak join continuations)
page1.insert_text((50, y), "(A) 9.8 m/s2", fontsize=12)
page1.insert_text((200, y), "(B) 10 m/s2", fontsize=12)
y += 30

# Question 2 (Starts on this page, continues on next page)
page1.insert_text((50, y), "Q 2. Two blocks are connected by a massless string.", fontsize=12)
y += 20
page1.insert_text((60, y), "The friction coefficient is 0.5.", fontsize=12)

# Page 2
page2 = doc.new_page(width=600, height=800)
y2 = 50

# Continuation of Q2
page2.insert_text((60, y2), "Find the tension in the string.", fontsize=12)
y2 += 40

# Question 3 (With weak join/stranded numbers)
page2.insert_text((50, y2), "3. Calculate the integral of x^2.", fontsize=12)
y2 += 20
page2.insert_text((55, y2), "45", fontsize=12) # Some stranded number without alpha

doc.save("test_jee.pdf")
print("PDF created successfully.")
