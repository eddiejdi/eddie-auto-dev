package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of the Jira struct
func TestCreateIssue(t *testing.T) {
	j := &Jira{}
	err := j.CreateIssue("New Feature Request", "Implement a new feature")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue method of the Jira struct
func TestUpdateIssue(t *testing.T) {
	j := &Jira{}
	err := j.UpdateIssue(123, "New Feature Request", "Implement a new feature")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestSubmitBuild tests the SubmitBuild method of the GoAgent struct
func TestSubmitBuild(t *testing.T) {
	goAgent := &GoAgent{}
	err := goAgent.SubmitBuild(123, "SUCCESS")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}