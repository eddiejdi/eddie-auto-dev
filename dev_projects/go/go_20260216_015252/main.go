package main

import (
	"fmt"
	"log"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API
type GoAgentClient interface {
	SendStatus(status string) error
}

// JiraClientImpl implementa a interface JiraClient
type JiraClientImpl struct{}

func (j *JiraClientImpl) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentClientImpl implementa a interface GoAgentClient
type GoAgentClientImpl struct{}

func (g *GoAgentClientImpl) SendStatus(status string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending status: %s\n", status)
	return nil
}

// JiraJiraClient é uma implementação concreta da interface JiraClient
type JiraJiraClient struct{}

func (j *JiraJiraClient) CreateIssue(title string, description string) error {
	client := &JiraClientImpl{}
	return client.CreateIssue(title, description)
}

// GoAgentGoAgentClient é uma implementação concreta da interface GoAgentClient
type GoAgentGoAgentClient struct{}

func (g *GoAgentGoAgentClient) SendStatus(status string) error {
	client := &GoAgentClientImpl{}
	return client.SendStatus(status)
}

// main é a função principal do programa
func main() {
	jiraClient := &JiraJiraClient{}
	goAgentClient := &GoAgentGoAgentClient{}

	err := jiraClient.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		log.Fatalf("Error creating Jira issue: %v", err)
	}

	err = goAgentClient.SendStatus("Running")
	if err != nil {
		log.Fatalf("Error sending Go Agent status: %v", err)
	}
}