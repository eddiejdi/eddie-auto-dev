package main

import (
	"fmt"
	"log"

	"github.com/jenkinsci/go-agent/v4"
	"github.com/jenkinsci/go-agent/v4/configfile"
)

func main() {
	// Configuração do agent
	config := configfile.Config{
		Name: "Go Agent",
	}

	// Cria o agente
	agent, err := goagent.NewAgent(config)
	if err != nil {
		log.Fatalf("Error creating agent: %v", err)
	}
	defer agent.Close()

	// Inicia o servidor HTTP do agent
	go agent.StartHTTPServer()

	fmt.Println("Go Agent is running...")
	select {}
}