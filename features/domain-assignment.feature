Feature: Domain Assignment

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled admin "admin@palmetto.app.wisp.llc" with password "AdminPass123!"
    And an enrolled user "contributor@palmetto.app.wisp.llc" with password "UserPass123!" and roles "contributor"
    And an enrolled user "reviewer@palmetto.app.wisp.llc" with password "UserPass123!" and roles "reviewer"
    And an enrolled user "contributor2@palmetto.app.wisp.llc" with password "UserPass123!" and roles "contributor"
    And an enrolled user "reviewer2@palmetto.app.wisp.llc" with password "UserPass123!" and roles "reviewer"
    And domain "AC" is ready for assignment

  Scenario: ASSN-01 Admin assigns contributor and reviewer
    Given "admin@palmetto.app.wisp.llc" is signed in
    When the admin assigns domain "AC" to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    Then domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is notified of domain "AC" assignment as contributor
    And "reviewer@palmetto.app.wisp.llc" is notified of domain "AC" assignment as reviewer

  Scenario: ASSN-02 One contributor, one reviewer at a time
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    When the admin assigns domain "AC" to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer
    Then domain "AC" is assigned to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is notified of domain "AC" unassignment as contributor
    And "reviewer@palmetto.app.wisp.llc" is notified of domain "AC" unassignment as reviewer

  Scenario: ASSN-03 Reassignment preserves work
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" has answered a question in domain "AC"
    When the admin assigns domain "AC" to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer
    Then the answer in domain "AC" still exists
    And domain "AC" is assigned to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer

  Scenario: ASSN-04 Contributors see only assigned domains
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And domain "PE" is assigned to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    When "contributor@palmetto.app.wisp.llc" is signed in
    And they request their assigned domains
    Then they see domain "AC" with role "contributor"
    And they do not see domain "PE"

  Scenario: ASSN-05 Unassigned domains flagged to admin
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    When the admin requests unassigned domains
    Then domain "PE" is flagged as missing "contributor, reviewer"
    And domain "AC" is not flagged
