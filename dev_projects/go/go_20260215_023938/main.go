package main

import (
	"fmt"
	"net/http"
	"time"

	"github.com/jira/go-jira/v2"
)

type JiraClient struct {
	client *jira.Client
}

func (jc *JiraClient) CreateIssue(summary, description string) (*jira.Issue, error) {
	createIssue := &jira.CreateIssueInput{
		Fields: &jira.Fields{
			Summary:    summary,
			Description: description,
		},
	}
	return jc.client.CreateIssue(createIssue)
}

func (jc *JiraClient) GetIssues() ([]*jira.Issue, error) {
	return jc.client.Search(&jira.SearchOptions{Jql: "project = YOUR_PROJECT"})
}

func main() {
	jiraClient := &JiraClient{
		client: jira.NewClient("YOUR_JIRA_URL", "YOUR_API_TOKEN"),
	}

	issue, err := jiraClient.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}
	fmt.Printf("Created issue with ID: %s\n", issue.ID)

	issues, err := jiraClient.GetIssues()
	if err != nil {
		fmt.Println("Error getting issues:", err)
		return
	}

	for _, issue := range issues {
		fmt.Printf("Issue ID: %s, Summary: %s\n", issue.ID, issue.Fields.Summary)
	}
}