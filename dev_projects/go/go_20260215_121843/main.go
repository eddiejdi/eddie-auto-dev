package main

import (
	"fmt"
	"log"
)

// JiraClient é a interface para interagir com a API do Jira
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent
type GoAgentClient interface {
	SendStatus(status string) error
}

// JiraService é uma implementação da interface JiraClient
type JiraService struct{}

func (js *JiraService) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s\n", title)
	return nil
}

// GoAgentService é uma implementação da interface GoAgentClient
type GoAgentService struct{}

func (gas *GoAgentService) SendStatus(status string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending status to Go Agent: %s\n", status)
	return nil
}

// JiraTracker é uma classe que utiliza os serviços para gerenciar atividades no Jira e o Go Agent
type JiraTracker struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

func (jt *JiraTracker) TrackActivity(title, description string) error {
	err := jt.jiraClient.CreateIssue(title, description)
	if err != nil {
		return fmt.Errorf("Failed to create issue in Jira: %v", err)
	}
	fmt.Println("Issue created successfully in Jira")

	err = jt.goAgentClient.SendStatus("In progress")
	if err != nil {
		return fmt.Errorf("Failed to send status to Go Agent: %v", err)
	}
	fmt.Println("Status sent to Go Agent")

	return nil
}

func main() {
	jiraClient := &JiraService{}
	goAgentClient := &GoAgentService{}

	tracker := JiraTracker{jiraClient, goAgentClient}

	err := tracker.TrackActivity("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		log.Fatalf("Error tracking activity: %v", err)
	}
}