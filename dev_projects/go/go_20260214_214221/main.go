package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API
type GoAgentClient interface {
	SendStatus(status string) error
}

// JiraAPI é uma implementação da interface JiraClient
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// GoAgentAPI é uma implementação da interface GoAgentClient
type GoAgentAPI struct{}

func (g *GoAgentAPI) SendStatus(status string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending status '%s'\n", status)
	return nil
}

// JiraIntegration realiza a integração com o Jira e Go Agent
type JiraIntegration struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

func (ji *JiraIntegration) Integrate() error {
	// Simulação de chamada à API do Jira para criar um issue
	err := ji.jiraClient.CreateIssue("Test Issue", "This is a test issue created by Go Agent")
	if err != nil {
		return err
	}

	// Simulação de chamada à API do Go Agent para enviar o status do processo
	err = ji.goAgentClient.SendStatus("Running")
	if err != nil {
		return err
	}

	fmt.Println("Integration successful!")
	return nil
}

func main() {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	integration := &JiraIntegration{jira, goAgent}
	err := integration.Integrate()
	if err != nil {
		fmt.Println("Error integrating:", err)
	} else {
		fmt.Println("Integration completed successfully!")
	}
}