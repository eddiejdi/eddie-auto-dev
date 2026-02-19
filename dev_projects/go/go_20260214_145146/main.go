package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v4"
)

// JiraClient representa a conexão com o Jira
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url, token string) (*JiraClient, error) {
	jiraClient := &JiraClient{}
	config := jira.Config{
		URL:     url,
		User:    "your_username",
		Token:   token,
	}
	client, err := jira.New(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %v", err)
	}
	jiraClient.client = client
	return jiraClient, nil
}

// CreateIssue cria uma nova tarefa no Jira
func (jiraClient *JiraClient) CreateIssue(summary string, description string) (*jira.Issue, error) {
	projectKey := "YOUR_PROJECT_KEY" // Substitua pelo código do projeto em Jira
	issueType := "task"             // Substitua pelo tipo de tarefa em Jira

	fields := map[string]interface{}{
		"project": &jira.Project{
			Key: projectKey,
		},
		"summary": summary,
		"description": description,
	}

	issue, err := jiraClient.client.CreateIssue(fields)
	if err != nil {
		return nil, fmt.Errorf("failed to create issue: %v", err)
	}
	fmt.Printf("Created issue: %+v\n", issue)
	return issue, nil
}

// MonitorIssues monitora as tarefas do Jira
func (jiraClient *JiraClient) MonitorIssues() {
	for {
		issues, err := jiraClient.client.Search(&jira.SearchOptions{
			Query: "project=YOUR_PROJECT_KEY AND status!=done",
		})
		if err != nil {
			log.Printf("Failed to search issues: %v", err)
			continue
		}

		for _, issue := range issues.Items {
			fmt.Printf("Issue ID: %s, Status: %s\n", issue.ID, issue.Fields.Status.Name)
		}
		time.Sleep(5 * time.Minute) // Monitorar cada 5 minutos
	}
}

func main() {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	issue, err := jiraClient.CreateIssue("New Task", "This is a new task for the project.")
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	go jiraClient.MonitorIssues()

	fmt.Println("Press Ctrl+C to exit the program.")
	select {}
}