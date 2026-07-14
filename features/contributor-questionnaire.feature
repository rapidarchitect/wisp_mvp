Feature: Contributor questionnaire flow

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled user "contributor@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "contributor"
    And an enrolled user "reviewer@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "reviewer"
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is signed in

  Scenario: QSTN-01 Answering a question generates up to 3 follow-ups
    Given a seeded question "Do you restrict physical access to servers?" in domain "AC"
    When "contributor@palmetto.app.wisp.llc" answers "yes" to the question
    Then the response contains between 1 and 3 follow-up questions

  Scenario: QSTN-04 Skipped questions block submission
    Given a seeded question "Do you perform background checks?" in domain "AC"
    When "contributor@palmetto.app.wisp.llc" skips the question
    Then the domain "AC" progress shows submit_ready false

  Scenario: QSTN-05 Contributor saves progress and resumes
    Given a seeded question "Do you encrypt laptops?" in domain "AC"
    When "contributor@palmetto.app.wisp.llc" answers "yes" to the question
    And "contributor@palmetto.app.wisp.llc" signs out
    And "contributor@palmetto.app.wisp.llc" is signed in
    Then the domain "AC" progress shows the same answer and follow-ups

  Scenario: QSTN-06 AI outage waives follow-ups gracefully
    Given a seeded question "Do you have an incident response plan?" in domain "AC"
    And the follow-up LLM is configured to fail
    When "contributor@palmetto.app.wisp.llc" answers "yes" to the question
    Then the answer follow-up state is "waived"
    And the contributor receives a "followups_waived" notification
    And the domain "AC" progress shows submit_ready true

  Scenario: QSTN-02 AI compiles the domain final answer
    Given a fully answered domain "AC" for "contributor@palmetto.app.wisp.llc"
    When "contributor@palmetto.app.wisp.llc" compiles domain "AC"
    Then the compiled answer narrative is non-empty
    And a "domain_compiled" audit event exists for domain "AC"

  Scenario: QSTN-03 Contributor submits the domain for review
    Given a compiled domain "AC" for "contributor@palmetto.app.wisp.llc"
    When "contributor@palmetto.app.wisp.llc" submits domain "AC"
    Then the domain "AC" status is "in_review"
    And the reviewer receives a "domain_submitted" notification
