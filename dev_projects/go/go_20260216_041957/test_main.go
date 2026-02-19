package main_test

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of JiraService
func TestCreateIssue(t *testing.T) {
	jiraClient := &JiraAPI{}
	jiraService := JiraService{client: jiraClient}

	err := jiraService.CreateIssue("Bug in application", "The application crashes on login")
	if err != nil {
		t.Errorf("CreateIssue failed with error: %v", err)
	}
}

// TestTrackActivity tests the TrackActivity method of GoAgentService
func TestTrackActivity(t *testing.T) {
	goAgentClient := &GoAgentAPI{}
	goAgentService := GoAgentService{client: goAgentClient}

	err := goAgentService.TrackActivity("User logged in successfully")
	if err != nil {
		t.Errorf("TrackActivity failed with error: %v", err)
	}
}