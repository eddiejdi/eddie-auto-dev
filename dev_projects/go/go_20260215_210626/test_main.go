package main_test

import (
	"testing"
)

func TestCreateTask(t *testing.T) {
	config := &goagentjira.Config{
		JiraURL:    "https://your-jira-instance.atlassian.net",
		Username:  "your-username",
		Password:  "your-password",
	}

	client, err := goagentjira.NewClient(config)
	if err != nil {
		t.Fatalf("Failed to create Go Agent client: %v", err)
	}

	title := "Bug in Go Agent integration"
	description := "We need a better way to integrate Go Agent with Jira."

	err = client.CreateIssue(&goagentjira.Issue{
		Title:    title,
		Description: description,
		Type: &goagentjira.Type{
			Name: "Bug",
		},
	})
	if err != nil {
		t.Errorf("Failed to create task: %v", err)
	}
}

func TestUpdateTask(t *testing.T) {
	config := &goagentjira.Config{
		JiraURL:    "https://your-jira-instance.atlassian.net",
		Username:  "your-username",
		Password:  "your-password",
	}

	client, err := goagentjira.NewClient(config)
	if err != nil {
		t.Fatalf("Failed to create Go Agent client: %v", err)
	}

	taskID := "12345"
	title := "Bug in Go Agent integration"
	description := "The current implementation of the integration is not working as expected."

	err = client.UpdateIssue(&goagentjira.Issue{
		ID:       taskID,
		Title:    title,
		Description: description,
	})
	if err != nil {
		t.Errorf("Failed to update task: %v", err)
	}
}

func TestDeleteTask(t *testing.T) {
	config := &goagentjira.Config{
		JiraURL:    "https://your-jira-instance.atlassian.net",
		Username:  "your-username",
		Password:  "your-password",
	}

	client, err := goagentjira.NewClient(config)
	if err != nil {
		t.Fatalf("Failed to create Go Agent client: %v", err)
	}

	taskID := "12345"

	err = client.DeleteIssue(taskID)
	if err != nil {
		t.Errorf("Failed to delete task: %v", err)
	}
}