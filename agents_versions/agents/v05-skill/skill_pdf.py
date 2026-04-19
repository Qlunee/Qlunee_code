from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors

def create_skill_pdf():
    # Create PDF document
    doc = SimpleDocTemplate(
        "SKILL.pdf",
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=36,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#7F8C8D'),
        spaceAfter=40,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2980B9'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        leading=16
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['BodyText'],
        fontSize=11,
        leftIndent=20,
        spaceAfter=8,
        leading=14
    )
    
    # Title
    elements.append(Paragraph("SKILL", title_style))
    elements.append(Paragraph("The Key to Personal and Professional Excellence", subtitle_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Introduction
    elements.append(Paragraph("What is Skill?", heading_style))
    elements.append(Paragraph(
        "A skill is the learned ability to perform an action with determined results, often within a given amount of time, energy, or both. "
        "Skills can be divided into domain-general skills (such as the ability to learn) and domain-specific skills (such as playing a musical instrument). "
        "In the journey of personal and professional development, skills serve as the building blocks that enable individuals to achieve their goals and contribute meaningfully to society.",
        body_style
    ))
    elements.append(Spacer(1, 0.1*inch))
    
    # Types of Skills
    elements.append(Paragraph("Types of Skills", heading_style))
    
    elements.append(Paragraph("<b>1. Hard Skills (Technical Skills)</b>", body_style))
    elements.append(Paragraph(
        "• Programming and software development<br/>"
        "• Data analysis and statistics<br/>"
        "• Foreign languages<br/>"
        "• Project management<br/>"
        "• Financial analysis",
        bullet_style
    ))
    
    elements.append(Paragraph("<b>2. Soft Skills (Interpersonal Skills)</b>", body_style))
    elements.append(Paragraph(
        "• Communication and active listening<br/>"
        "• Leadership and team management<br/>"
        "• Problem-solving and critical thinking<br/>"
        "• Emotional intelligence<br/>"
        "• Adaptability and flexibility",
        bullet_style
    ))
    
    elements.append(Paragraph("<b>3. Transferable Skills</b>", body_style))
    elements.append(Paragraph(
        "• Time management<br/>"
        "• Organization and planning<br/>"
        "• Creativity and innovation<br/>"
        "• Research and analysis<br/>"
        "• Negotiation and persuasion",
        bullet_style
    ))
    elements.append(Spacer(1, 0.1*inch))
    
    # The Importance of Skill Development
    elements.append(Paragraph("The Importance of Skill Development", heading_style))
    elements.append(Paragraph(
        "In today's rapidly evolving world, skill development is not just an option—it's a necessity. "
        "Technological advancements, economic shifts, and changing workplace dynamics require individuals to continuously update and expand their skill sets. "
        "Those who invest in learning new skills position themselves for better career opportunities, higher earning potential, and greater job security.",
        body_style
    ))
    elements.append(Paragraph(
        "Moreover, skill development enhances self-confidence and personal satisfaction. "
        "Mastering a new skill provides a sense of accomplishment and opens doors to new experiences and relationships.",
        body_style
    ))
    elements.append(Spacer(1, 0.1*inch))
    
    # How to Develop Skills
    elements.append(Paragraph("How to Develop Skills Effectively", heading_style))
    elements.append(Paragraph(
        "<b>1. Set Clear Goals:</b> Define what you want to achieve and break it down into manageable steps.<br/><br/>"
        "<b>2. Practice Deliberately:</b> Focus on specific areas of improvement rather than just repeating what you already know.<br/><br/>"
        "<b>3. Seek Feedback:</b> Constructive criticism from mentors, peers, or instructors helps identify blind spots.<br/><br/>"
        "<b>4. Embrace Failure:</b> Mistakes are valuable learning opportunities that provide insights for improvement.<br/><br/>"
        "<b>5. Stay Consistent:</b> Regular practice, even in small amounts, yields better results than sporadic intensive sessions.<br/><br/>"
        "<b>6. Teach Others:</b> Explaining concepts to others reinforces your own understanding and reveals gaps in knowledge.",
        body_style
    ))
    elements.append(Spacer(1, 0.1*inch))
    
    # The Future of Skills
    elements.append(Paragraph("The Future of Skills", heading_style))
    elements.append(Paragraph(
        "As we move further into the 21st century, certain skills are becoming increasingly valuable. "
        "Digital literacy, artificial intelligence understanding, sustainability awareness, and cross-cultural competence are emerging as critical capabilities. "
        "The ability to learn continuously and adapt to new situations—often called 'learning agility'—may be the most important skill of all.",
        body_style
    ))
    elements.append(Spacer(1, 0.1*inch))
    
    # Conclusion
    elements.append(Paragraph("Conclusion", heading_style))
    elements.append(Paragraph(
        "Skills are the currency of the modern world. Whether you're looking to advance your career, pursue a passion, or simply become a more well-rounded individual, "
        "investing in skill development is one of the most rewarding endeavors you can undertake. "
        "Remember: every expert was once a beginner. The journey of skill acquisition is lifelong, and every step forward is a step toward unlocking your full potential.",
        body_style
    ))
    elements.append(Spacer(1, 0.3*inch))
    
    # Quote
    quote_style = ParagraphStyle(
        'Quote',
        parent=styles['Italic'],
        fontSize=12,
        textColor=colors.HexColor('#555555'),
        alignment=TA_CENTER,
        leftIndent=30,
        rightIndent=30,
        spaceBefore=10,
        spaceAfter=10
    )
    elements.append(Paragraph(
        '"The only skill that will be important in the 21st century is the skill of learning new skills. Everything else will become obsolete over time."<br/>— Peter Drucker',
        quote_style
    ))
    
    # Build PDF
    doc.build(elements)
    print("PDF created successfully: SKILL.pdf")

if __name__ == "__main__":
    create_skill_pdf()
