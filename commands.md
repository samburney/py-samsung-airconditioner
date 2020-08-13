## Commands

### Auth
```
<Request Type="GetToken" />
<Request Type="AuthToken"><User Token="{token}"/></Request>
```

### Get
```
<Request Type="DeviceState" DUID="{duid}"></Request>
<Request Type="DeviceState"><State DUID="{duid}"><Attr ID="{attr}" /></State></Request>
```

### Set
```
<Request Type="DeviceControl"><Control CommandID="{random_string}" DUID="{duid}"><Attr ID="{attr}" Value="{value}" /></Control></Request>
```
