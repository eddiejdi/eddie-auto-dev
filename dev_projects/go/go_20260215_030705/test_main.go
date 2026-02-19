package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of the JiraAPI struct
func TestCreateIssue(t *testing.T) {
	jira := &JiraAPI{}
	err := jira.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Error creating issue: %v", err)
	}
}

// TestTickleJob tests the TickleJob method of the GoAgentAPI struct
func TestTickleJob(t *testing.T) {
	goAgent := &GoAgentAPI{}
	err := goAgent.TickleJob("12345")
	if err != nil {
		t.Errorf("Error tickling job: %v", err)
	}
}

// TestCreateAndTickleIssue tests the CreateAndTickleIssue method of the JiraService struct
func TestCreateAndTickleIssue(t *testing.T) {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	service := &JiraService{jira, goAgent}

	err := service.CreateAndTickleIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Error creating and tickling issue: %v", err)
	}
}