"""Public, unscored review questions; no private factor registry or rubric."""
CHECK_VERSION = "public-review-questions.v1"
CHECKS = (
    ("page_labels", "Search Lens", "Page labels", "Do the captured title, description and visible headings describe the page a visitor actually gets?"),
    ("link_meaning", "Search Lens", "Link meaning", "Do the followed links and their surrounding text explain the destination accurately?"),
    ("structured_agreement", "AI Lens", "Declared information", "Where captured structured declarations describe the same offer or organization as visible text, do they agree? Missing optional markup alone is not an issue."),
    ("answer_context", "AI Lens", "Answers in context", "Can the question raised by the selected task be answered from the inspected information with its necessary qualifications?"),
    ("information_agreement", "AI Lens", "Information agreement", "Do statements about the same thing agree across the inspected pages? Account for different dates, audiences and conditions; quote both sides of a claimed conflict."),
    ("offer_clarity", "Human Lens", "Offer clarity", "Can a visitor tell what is offered and whether it fits their stated goal from the inspected page?"),
    ("decision_terms", "Human Lens", "Terms at the decision", "Are relevant costs, eligibility and important conditions available where the inspected journey asks for a decision?"),
    ("claim_support", "Human Lens", "Supporting evidence", "Do important claims used in this journey have inspectable supporting information? Unvisited proof is unknown; do not demand testimonials or badges for every site."),
    ("next_step", "Human Lens", "Next step", "Does the observed path explain how to continue and deliver the promised next step within the permitted navigation scope? A handoff or policy stop is not itself a defect."),
)
CHECK_BY_ID = {row[0]: row for row in CHECKS}
OUTCOMES = ("issue_observed", "no_issue_observed", "inconclusive", "unavailable", "not_applicable")

def review_questions():
    return [{"id": key, "lens": lens, "name": name, "question": question} for key,lens,name,question in CHECKS]
