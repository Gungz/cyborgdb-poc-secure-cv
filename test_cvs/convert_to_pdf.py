#!/usr/bin/env python3
"""Convert text CV files to PDF format."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER

def convert_txt_to_pdf(txt_path, pdf_path):
    """Convert a text file to PDF."""
    # Read the text content
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Create styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CVTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    heading_style = ParagraphStyle(
        'CVHeading',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor='#2c3e50'
    )
    
    normal_style = ParagraphStyle(
        'CVNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=4
    )
    
    # Build the PDF content
    story = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        
        # Escape special characters for reportlab
        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Determine style based on content
        if line == 'CURRICULUM VITAE':
            story.append(Paragraph(line, title_style))
        elif line.isupper() and len(line) > 3:
            story.append(Paragraph(f"<b>{line}</b>", heading_style))
        elif line.startswith('- '):
            story.append(Paragraph(f"• {line[2:]}", normal_style))
        elif '|' in line and any(word in line for word in ['Engineer', 'Manager', 'Analyst', 'Designer', 'Scientist', 'Executive', 'Coordinator', 'Specialist', 'Administrator']):
            # Job title line
            story.append(Paragraph(f"<b>{line}</b>", normal_style))
        else:
            story.append(Paragraph(line, normal_style))
    
    # Build PDF
    doc.build(story)
    print(f"Created: {pdf_path}")

def main():
    """Convert all text CVs to PDF."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Find all .txt files
    txt_files = [f for f in os.listdir(script_dir) if f.endswith('.txt')]
    
    for txt_file in sorted(txt_files):
        txt_path = os.path.join(script_dir, txt_file)
        pdf_file = txt_file.replace('.txt', '.pdf')
        pdf_path = os.path.join(script_dir, pdf_file)
        
        try:
            convert_txt_to_pdf(txt_path, pdf_path)
        except Exception as e:
            print(f"Error converting {txt_file}: {e}")

if __name__ == '__main__':
    main()
