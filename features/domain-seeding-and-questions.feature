Feature: Domain Seeding and Questions

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled admin "admin@palmetto.app.wisp.llc" with password "AdminPass123!"

  Scenario: 14 domains seeded, 5-10 questions each (SEED-01)
    Given "admin@palmetto.app.wisp.llc" is signed in
    When the admin seeds all domains
    Then 14 domains exist
    And each domain has between 5 and 10 questions
    And all questions are yes-no questions

  Scenario: Demo company after deployment (SEED-02)
    When the operator runs the seed-demo command
    Then a demo tenant "demo" is provisioned
    And the demo tenant has 14 domains
    And each domain has between 5 and 10 questions

  Scenario: Research outage degrades gracefully (SEED-03)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And the LLM is set to fail
    When the admin seeds all domains
    Then seeding is marked as pending for at least one domain
    And no exception is raised

  Scenario: Admin adds custom question (SEED-04)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is ready
    When the admin adds a custom question "Do you require MFA on all remote access?" to domain "AC"
    Then domain "AC" has 6 enabled questions
    And the new question has origin "admin"

  Scenario: Admin disables seeded question (SEED-05)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is ready
    And the admin has added a custom question to domain "AC"
    When the admin disables a seeded question in domain "AC"
    Then the disabled question is hidden
    And domain "AC" has 5 enabled questions

  Scenario: Regeneration only when unanswered (SEED-06)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is ready
    When the admin regenerates questions for domain "AC"
    Then domain "AC" has fresh seeded questions
    When a contributor answers a question in domain "AC"
    And the admin regenerates questions for domain "AC"
    Then the regeneration is rejected with "domain_has_answers"
