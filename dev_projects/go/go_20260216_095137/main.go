package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para a comunicação com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é a interface para a comunicação com o Go Agent API
type GoAgentClient interface {
	SendEvent(eventName string, eventData map[string]interface{}) error
}

// JiraAPI é uma implementação da interface JiraClient
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title string, description string) error {
	// Simulação de requisição HTTP para criar um issue no Jira
	resp, err := http.Post("https://your-jira-instance.com/rest/api/2/issue", "application/json", nil)
	if err != nil {
		return fmt.Errorf("Failed to create issue: %v", err)
	}
	defer resp.Body.Close()

	// Verificar o status da resposta
	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("Issue creation failed with status code %d", resp.StatusCode)
	}

	fmt.Println("Issue created successfully")
	return nil
}

// GoAgentAPI é uma implementação da interface GoAgentClient
type GoAgentAPI struct{}

func (g *GoAgentAPI) SendEvent(eventName string, eventData map[string]interface{}) error {
	// Simulação de requisição HTTP para enviar um evento ao Go Agent
	resp, err := http.Post("https://your-go-agent-instance.com/api/v1/events", "application/json", nil)
	if err != nil {
		return fmt.Errorf("Failed to send event: %v", err)
	}
	defer resp.Body.Close()

	// Verificar o status da resposta
	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("Event sending failed with status code %d", resp.StatusCode)
	}

	fmt.Println("Event sent successfully")
	return nil
}

func main() {
	jiraClient := &JiraAPI{}
	goAgentClient := &GoAgentAPI{}

	err := jiraClient.CreateIssue("Test Issue", "This is a test issue created by Go Agent and Jira API integration.")
	if err != nil {
		fmt.Println(err)
		return
	}

	err = goAgentClient.SendEvent("test_event", map[string]interface{}{
		"event_name":  "test_event",
		"event_data": map[string]string{
			"user": "user123",
		},
	})
	if err != nil {
		fmt.Println(err)
		return
	}
}