package main_test

import (
	"testing"
	"github.com/yourusername/go-agent-jira"
)

func TestCreateTask(t *testing.T) {
	config := &jira.Config{
		BaseURL: "https://your-jira-instance.atlassian.net",
		UserName: "your-username",
		Password: "your-password",
	}

	client, err := jira.NewClient(config)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}

	taskID := "12345"
	err = client.CreateIssue(&jira.Issue{
		Title:    taskID,
		Description: "This is a test task created by Go Agent",
	})
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}

func TestUpdateTask(t *testing.T) {
	config := &jira.Config{
		BaseURL: "https://your-jira-instance.atlassian.net",
		UserName: "your-username",
		Password: "your-password",
	}

	client, err := jira.NewClient(config)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}

	taskID := "12345"
	err = client.UpdateIssue(&jira.Issue{
		ID:      taskID,
		Title:    "Updated Test Task",
		Description: "This is an updated test task created by Go Agent",
	})
	if err != nil {
		t.Errorf("Failed to update issue: %v", err)
	}
}

func TestDeleteTask(t *testing.T) {
	config := &jira.Config{
		BaseURL: "https://your-jira-instance.atlassian.net",
		UserName: "your-username",
		Password: "your-password",
	}

	client, err := jira.NewClient(config)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}

	taskID := "12345"
	err = client.DeleteIssue(&jira.Issue{
		ID: taskID,
	})
	if err != nil {
		t.Errorf("Failed to delete issue: %v", err)
	}
}