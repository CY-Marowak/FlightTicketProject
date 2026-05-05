Trace the price of flights tickets. <br>
Using api data from: https://rapidapi.com/DataCrawler/api/google-flights2 <br>

This is desktop version with backend code. I'll update it on cloud if needed.

graph TD
    %% 前端用戶端層
    subgraph Clients [前端展示層 - Frontend]
        Web[React Web App]
        Desktop[PyQt Desktop Client]
        Mobile[Expo React Native App]
    end

    %% API 閘道層
    subgraph API_Layer [後端核心層 - Backend]
        Flask[Flask RESTful API]
        SocketIO[Socket.io Real-time]
        Scheduler[APScheduler 定時任務]
    end

    %% 外部服務與資料庫
    subgraph Services [外部服務與資料層 - Infrastructure]
        DB[(PostgreSQL Database)]
        R_API[RapidAPI - Flight Data]
        FCM[Firebase Cloud Messaging]
    end

    %% 連線關係
    Web <-->|REST / WebSocket| Flask
    Desktop <-->|REST| Flask
    Mobile <-->|REST / Push Notification| Flask
    
    Flask <--> DB
    Scheduler -->|Trigger| Flask
    Flask -->|Fetch Flight Info| R_API
    Flask -->|Send Push| FCM
    FCM -.->|Push Notification| Mobile

    %% 樣式設定
    style Flask fill:#f9f,stroke:#333,stroke-width:2px
    style DB fill:#7fe,stroke:#333,stroke-width:2px
    style R_API fill:#fff4dd,stroke:#d4a017,stroke-width:2px
    style FCM fill:#ffcb2b,stroke:#333,stroke-width:2px
