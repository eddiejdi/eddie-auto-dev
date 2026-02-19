package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API
type GoAgentClient interface {
	SendEvent(eventName string, eventData map[string]interface{}) error
}

// JiraAPI implementa a interface JiraClient
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// GoAgentAPI implementa a interface GoAgentClient
type GoAgentAPI struct{}

func (g *GoAgentAPI) SendEvent(eventName string, eventData map[string]interface{}) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending event '%s' with data: %v\n", eventName, eventData)
	return nil
}

// JiraJiraClient é um adaptador que converte entre JiraAPI e GoAgentAPI
type JiraJiraClient struct {
	jira JiraAPI
	goa  GoAgentAPI
}

func (j *JiraJiraClient) CreateIssue(title string, description string) error {
	return j.jira.CreateIssue(title, description)
}

func (g *JiraJiraClient) SendEvent(eventName string, eventData map[string]interface{}) error {
	return g.goa.SendEvent(eventName, eventData)
}

// main é a função principal do programa
func main() {
	jira := JiraAPI{}
	goa := GoAgentAPI{}

	jiraGoa := JiraJiraClient{jira: jira, goa: goa}

	// Criando um novo issue no Jira
	err := jiraGoa.CreateIssue("Test Issue", "This is a test issue created by Go Agent and Jira.")
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}

	// Enviando um evento para o Go Agent
	eventData := map[string]interface{}{
		"event":   "test",
		"data":    "Hello, World!",
		"timeStamp": 1633072800,
	}
	err = jiraGoa.SendEvent("Test Event", eventData)
	if err != nil {
		fmt.Println("Error sending event:", err)
		return
	}

	fmt.Println("Issue created and event sent successfully.")
}