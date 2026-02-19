package main

import (
	"fmt"
	"log"

	"github.com/jenkinsci/go-agent/v4/client"
)

// JiraClient é a interface para interagir com o Jira API.
type JiraClient interface {
	CreateIssue(title, description string) error
}

// goAgentJiraClient implementa a JiraClient interface usando o Go Agent SDK.
type goAgentJiraClient struct{}

func (j *goAgentJiraClient) CreateIssue(title, description string) error {
	agent := client.NewAgent()
	err := agent.Connect("http://localhost:8080")
	if err != nil {
		return fmt.Errorf("failed to connect to Go Agent: %v", err)
	}

	jiraService := agent.GetService("jira")

	issue := &client.Issue{
		Title:    title,
		Description: description,
	}

	err = jiraService.CreateIssue(issue)
	if err != nil {
		return fmt.Errorf("failed to create issue in Jira: %v", err)
	}

	fmt.Println("Issue created successfully")
	return nil
}

func main() {
	client := goAgentJiraClient{}

	title := "New Feature Request"
	description := "Implement a new feature for the application."

	err := client.CreateIssue(title, description)
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}
}