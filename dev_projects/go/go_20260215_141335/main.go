package main

import (
	"fmt"
	"log"

	"github.com/jenkinsci/go-agent/v4/pkg/agent"
)

func main() {
	// Configuração do Go Agent
	config := agent.DefaultConfig()
	config.JiraServerURL = "https://your-jira-server.com"
	config.JiraUsername = "your-username"
	config.JiraPassword = "your-password"

	// Cria o Go Agent
	goAgent, err := agent.New(config)
	if err != nil {
		log.Fatalf("Failed to create Go Agent: %v", err)
	}

	// Inicia o Go Agent
	err = goAgent.Start()
	if err != nil {
		log.Fatalf("Failed to start Go Agent: %v", err)
	}
}