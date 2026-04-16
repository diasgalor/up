// GEE script gerado automaticamente a partir de fields.mbtiles (fazenda 3 - SAN_JORGE)
// Objetivo:
// 1) Buscar a ultima imagem Sentinel-2 com baixa cobertura de nuvem
// 2) Gerar compositos Janeiro-Fevereiro-Marco para analise da soja
// 3) Calcular NDVI e estatistica por talhao
// 4) Exportar imagens e tabelas para uso no app

var talhoesGeoJson = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[-53.173882, -18.7389], [-53.173909, -18.738824], [-53.173828, -18.738128], [-53.173828, -18.738931], [-53.173882, -18.7389]]], [[[-53.173828, -18.730853], [-53.174263, -18.731006], [-53.174568, -18.731031], [-53.175105, -18.731011], [-53.175212, -18.730985], [-53.176328, -18.730579], [-53.176532, -18.730518], [-53.176709, -18.730488], [-53.176795, -18.730452], [-53.176859, -18.730396], [-53.176966, -18.730254], [-53.177015, -18.730137], [-53.177025, -18.729974], [-53.176977, -18.729502], [-53.173828, -18.729502], [-53.173828, -18.730853]]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 41, "DESC_TALHA": "D1", "AREA_TOTAL": 76.82}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.17813, -18.708692], [-53.181832, -18.710887], [-53.183339, -18.711796], [-53.183715, -18.712004], [-53.183752, -18.712004], [-53.183811, -18.711948], [-53.184616, -18.710485], [-53.185641, -18.708692], [-53.17813, -18.708692]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 51, "DESC_TALHA": "F1", "AREA_TOTAL": 103.15}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.173828, -18.710612], [-53.173828, -18.721886], [-53.176762, -18.723644], [-53.177079, -18.723802], [-53.177138, -18.723797], [-53.17717, -18.723771], [-53.177744, -18.722694], [-53.178205, -18.721876], [-53.178297, -18.721693], [-53.178334, -18.721582], [-53.178404, -18.721516], [-53.17849, -18.721388], [-53.179396, -18.719778], [-53.179445, -18.71962], [-53.179632, -18.719361], [-53.179954, -18.718731], [-53.180587, -18.717634], [-53.180732, -18.717329], [-53.180861, -18.717156], [-53.181199, -18.716572], [-53.182738, -18.713803], [-53.18291, -18.713544], [-53.18321, -18.712949], [-53.183522, -18.712401], [-53.18365, -18.712203], [-53.183688, -18.712131], [-53.183693, -18.712076], [-53.183661, -18.712025], [-53.183613, -18.711989], [-53.178077, -18.708692], [-53.174896, -18.708692], [-53.173828, -18.710612]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 23, "DESC_TALHA": "C3", "AREA_TOTAL": 146.87}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.174837, -18.708692], [-53.173828, -18.708692], [-53.173828, -18.710506], [-53.174837, -18.708692]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 4, "DESC_TALHA": "A4", "AREA_TOTAL": 135.76}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.176939, -18.729375], [-53.176854, -18.729294], [-53.176677, -18.729223], [-53.17606, -18.72908], [-53.175856, -18.729024], [-53.175754, -18.728979], [-53.175647, -18.728903], [-53.175588, -18.728831], [-53.175486, -18.728633], [-53.17547, -18.728532], [-53.175518, -18.728354], [-53.176838, -18.724721], [-53.176939, -18.724457], [-53.1771, -18.724112], [-53.177133, -18.72401], [-53.1771, -18.723898], [-53.177068, -18.723858], [-53.1768, -18.72372], [-53.173828, -18.721932], [-53.173828, -18.729502], [-53.176977, -18.729502], [-53.176939, -18.729375]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 41, "DESC_TALHA": "D1", "AREA_TOTAL": 76.82}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.17894, -18.698763], [-53.178919, -18.698778], [-53.178887, -18.698849], [-53.175706, -18.706989], [-53.175695, -18.707056], [-53.175727, -18.707127], [-53.175738, -18.707274], [-53.17813, -18.708692], [-53.185641, -18.708692], [-53.186461, -18.707183], [-53.186708, -18.706781], [-53.186933, -18.706334], [-53.187148, -18.705989], [-53.18732, -18.705648], [-53.187561, -18.705231], [-53.187792, -18.704673], [-53.187808, -18.704566], [-53.18776, -18.704424], [-53.18769, -18.704357], [-53.187352, -18.704169], [-53.186375, -18.703524], [-53.185346, -18.702879], [-53.18327, -18.701517], [-53.181446, -18.700369], [-53.180142, -18.699505], [-53.179241, -18.698931], [-53.179026, -18.698768], [-53.17894, -18.698763]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 51, "DESC_TALHA": "F1", "AREA_TOTAL": 103.15}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.175668, -18.70733], [-53.17562, -18.707371], [-53.175513, -18.707553], [-53.174896, -18.708692], [-53.178077, -18.708692], [-53.175936, -18.707426], [-53.175743, -18.707325], [-53.175668, -18.70733]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 23, "DESC_TALHA": "C3", "AREA_TOTAL": 146.87}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.175121, -18.706817], [-53.175507, -18.707081], [-53.17555, -18.707071], [-53.175641, -18.707], [-53.175711, -18.706888], [-53.176897, -18.703865], [-53.177143, -18.703199], [-53.178881, -18.698814], [-53.178892, -18.698722], [-53.178812, -18.698641], [-53.177497, -18.697813], [-53.175786, -18.6967], [-53.17548, -18.696487], [-53.173828, -18.695435], [-53.173828, -18.706004], [-53.175121, -18.706817]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 33, "DESC_TALHA": "E3", "AREA_TOTAL": 89.58}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.175486, -18.707508], [-53.175523, -18.70736], [-53.175496, -18.707203], [-53.175437, -18.707101], [-53.175293, -18.706969], [-53.173828, -18.706044], [-53.173828, -18.708692], [-53.174837, -18.708692], [-53.175486, -18.707508]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 4, "DESC_TALHA": "A4", "AREA_TOTAL": 135.76}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.154704, -18.754389], [-53.154924, -18.755389], [-53.154967, -18.755471], [-53.155026, -18.755506], [-53.155096, -18.755516], [-53.1623, -18.755628], [-53.163276, -18.755613], [-53.163593, -18.755628], [-53.163668, -18.755603], [-53.163716, -18.755542], [-53.163711, -18.7554], [-53.163335, -18.753576], [-53.162702, -18.75031], [-53.153862, -18.75031], [-53.154704, -18.754389]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 13, "DESC_TALHA": "B3", "AREA_TOTAL": 168.27}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.163072, -18.752067], [-53.163148, -18.752555], [-53.163266, -18.753165], [-53.163786, -18.755643], [-53.164467, -18.755633], [-53.164843, -18.755654], [-53.167659, -18.755694], [-53.16819, -18.755715], [-53.170159, -18.75574], [-53.171473, -18.75574], [-53.171532, -18.75576], [-53.171602, -18.755755], [-53.17165, -18.755709], [-53.171623, -18.75542], [-53.171677, -18.753068], [-53.171715, -18.752225], [-53.171709, -18.751676], [-53.171752, -18.75031], [-53.162718, -18.75031], [-53.163072, -18.752067]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 34, "DESC_TALHA": "E4", "AREA_TOTAL": 100.86}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.171167, -18.729502], [-53.171339, -18.73094], [-53.171462, -18.731798], [-53.172358, -18.738687], [-53.172364, -18.738855], [-53.172326, -18.739139], [-53.172353, -18.7392], [-53.172417, -18.739226], [-53.172605, -18.739159], [-53.173828, -18.738931], [-53.173828, -18.738128], [-53.173673, -18.736802], [-53.173431, -18.734506], [-53.173088, -18.731504], [-53.17304, -18.731214], [-53.172916, -18.730813], [-53.172954, -18.730726], [-53.173056, -18.730676], [-53.173158, -18.73067], [-53.173656, -18.730792], [-53.173828, -18.730853], [-53.173828, -18.729502], [-53.171167, -18.729502]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 41, "DESC_TALHA": "D1", "AREA_TOTAL": 76.82}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.158588, -18.729502], [-53.160358, -18.738423], [-53.16053, -18.739154], [-53.160583, -18.73922], [-53.160675, -18.739241], [-53.16112, -18.739246], [-53.169746, -18.739119], [-53.171843, -18.739119], [-53.172149, -18.739098], [-53.172278, -18.739012], [-53.172326, -18.738895], [-53.172321, -18.738636], [-53.171124, -18.729502], [-53.158588, -18.729502]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 22, "DESC_TALHA": "C2", "AREA_TOTAL": 199.45}}, {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[-53.172251, -18.739124], [-53.167284, -18.739175], [-53.160524, -18.739276], [-53.161265, -18.743091], [-53.161747, -18.745499], [-53.161796, -18.745641], [-53.161844, -18.745713], [-53.161951, -18.745799], [-53.162107, -18.745835], [-53.166586, -18.745865], [-53.16694, -18.745916], [-53.167005, -18.74589], [-53.167031, -18.745814], [-53.16708, -18.745774], [-53.167166, -18.745768], [-53.167326, -18.745794], [-53.167825, -18.745794], [-53.167879, -18.745733], [-53.167933, -18.745702], [-53.169858, -18.744808], [-53.170556, -18.744438], [-53.171967, -18.743594], [-53.17238, -18.7433], [-53.172669, -18.743015], [-53.172755, -18.742908], [-53.172771, -18.742858], [-53.172798, -18.742594], [-53.172718, -18.742157], [-53.172508, -18.74046], [-53.172337, -18.739226], [-53.172305, -18.739154], [-53.172251, -18.739124]]], [[[-53.17283, -18.74271], [-53.17283, -18.742873], [-53.172814, -18.742924], [-53.172686, -18.743086], [-53.172487, -18.743279], [-53.172251, -18.743477], [-53.171993, -18.743645], [-53.170427, -18.744559], [-53.169875, -18.744849], [-53.168866, -18.745321], [-53.168051, -18.745682], [-53.167906, -18.745758], [-53.16789, -18.745789], [-53.168319, -18.745733], [-53.168684, -18.745758], [-53.169161, -18.745753], [-53.169392, -18.745768], [-53.170293, -18.745723], [-53.170545, -18.745748], [-53.17165, -18.745743], [-53.171865, -18.745774], [-53.172122, -18.745779], [-53.17246, -18.745748], [-53.173147, -18.745784], [-53.1732, -18.745774], [-53.173238, -18.745738], [-53.173249, -18.745682], [-53.172948, -18.743513], [-53.172879, -18.742878], [-53.17283, -18.74271]]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 42, "DESC_TALHA": "D2", "AREA_TOTAL": 89.42}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.152928, -18.739358], [-53.156276, -18.739297], [-53.160304, -18.739251], [-53.160406, -18.739231], [-53.160455, -18.739195], [-53.160471, -18.739144], [-53.160465, -18.739104], [-53.160353, -18.738601], [-53.159387, -18.733769], [-53.15855, -18.729502], [-53.151855, -18.729502], [-53.151855, -18.739358], [-53.152928, -18.739358]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 12, "DESC_TALHA": "B2", "AREA_TOTAL": 175.12}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.160508, -18.739286], [-53.151855, -18.739378], [-53.151855, -18.740846], [-53.15244, -18.743594], [-53.152692, -18.744859], [-53.153862, -18.75031], [-53.162702, -18.75031], [-53.161297, -18.743381], [-53.160825, -18.740866], [-53.160508, -18.739286]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 13, "DESC_TALHA": "B3", "AREA_TOTAL": 168.27}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.161898, -18.74587], [-53.16186, -18.745895], [-53.161844, -18.745956], [-53.162718, -18.75031], [-53.171752, -18.75031], [-53.171822, -18.746779], [-53.171806, -18.7465], [-53.17179, -18.746464], [-53.171731, -18.746414], [-53.170727, -18.746287], [-53.170143, -18.74616], [-53.169778, -18.746099], [-53.169129, -18.746048], [-53.168244, -18.746028], [-53.167782, -18.745992], [-53.167525, -18.746012], [-53.167321, -18.746007], [-53.166624, -18.745895], [-53.164564, -18.74589], [-53.162509, -18.74586], [-53.161898, -18.74587]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 34, "DESC_TALHA": "E4", "AREA_TOTAL": 100.86}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.173227, -18.711715], [-53.172916, -18.712253], [-53.170352, -18.716943], [-53.16973, -18.71803], [-53.169156, -18.719087], [-53.169569, -18.719321], [-53.172074, -18.720855], [-53.173828, -18.721886], [-53.173828, -18.710612], [-53.173227, -18.711715]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 23, "DESC_TALHA": "C3", "AREA_TOTAL": 146.87}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.165835, -18.70924], [-53.167176, -18.709977], [-53.168035, -18.71048], [-53.168566, -18.710765], [-53.168705, -18.710826], [-53.168952, -18.710876], [-53.16973, -18.711268], [-53.170524, -18.711694], [-53.17113, -18.712086], [-53.171425, -18.712294], [-53.171849, -18.712599], [-53.172417, -18.713051], [-53.173828, -18.710506], [-53.173828, -18.708692], [-53.164875, -18.708692], [-53.165835, -18.70924]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 4, "DESC_TALHA": "A4", "AREA_TOTAL": 135.76}}, {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[-53.168989, -18.711044], [-53.168866, -18.711105], [-53.168839, -18.71113], [-53.165213, -18.716679], [-53.165208, -18.71675], [-53.165224, -18.716816], [-53.167064, -18.717908], [-53.167112, -18.717903], [-53.167203, -18.717832], [-53.167332, -18.717842], [-53.167369, -18.717807], [-53.167477, -18.717598], [-53.167595, -18.717446], [-53.167632, -18.717426], [-53.16775, -18.717441], [-53.167782, -18.717431], [-53.167863, -18.717299], [-53.167959, -18.71708], [-53.167933, -18.717014], [-53.167536, -18.716816], [-53.167503, -18.71677], [-53.167788, -18.716237], [-53.167788, -18.716201], [-53.167766, -18.716176], [-53.167611, -18.716059], [-53.1676, -18.716003], [-53.168136, -18.715094], [-53.168195, -18.715022], [-53.168297, -18.714961], [-53.168335, -18.714961], [-53.168448, -18.715007], [-53.169134, -18.715403], [-53.16959, -18.715688], [-53.169687, -18.715729], [-53.169821, -18.715698], [-53.16995, -18.715627], [-53.170046, -18.71552], [-53.170288, -18.71516], [-53.170331, -18.715129], [-53.17039, -18.715149], [-53.170964, -18.71551], [-53.171049, -18.71552], [-53.171087, -18.71548], [-53.172342, -18.713188], [-53.172342, -18.713092], [-53.172321, -18.713046], [-53.172128, -18.712863], [-53.171355, -18.712289], [-53.170454, -18.711694], [-53.169692, -18.711288], [-53.169242, -18.71107], [-53.16914, -18.711044], [-53.168989, -18.711044]]], [[[-53.156093, -18.708692], [-53.155171, -18.710658], [-53.155165, -18.71078], [-53.155214, -18.710856], [-53.155589, -18.711095], [-53.158566, -18.712868], [-53.159789, -18.713579], [-53.163518, -18.715815], [-53.165079, -18.71673], [-53.165122, -18.716704], [-53.165197, -18.716608], [-53.165701, -18.71582], [-53.168437, -18.711679], [-53.16878, -18.711095], [-53.168743, -18.710953], [-53.168598, -18.710831], [-53.164805, -18.708692], [-53.156093, -18.708692]]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 1, "DESC_TALHA": "A1", "AREA_TOTAL": 121.19}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.169853, -18.719631], [-53.169885, -18.719742], [-53.169917, -18.719976], [-53.170449, -18.724142], [-53.171167, -18.729502], [-53.173828, -18.729502], [-53.173828, -18.721932], [-53.172798, -18.721343], [-53.169858, -18.719559], [-53.169853, -18.719631]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 41, "DESC_TALHA": "D1", "AREA_TOTAL": 76.82}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.155053, -18.710876], [-53.155004, -18.710902], [-53.154956, -18.710968], [-53.154929, -18.71109], [-53.15494, -18.711247], [-53.155058, -18.711776], [-53.156442, -18.718701], [-53.157456, -18.723863], [-53.157515, -18.723929], [-53.157842, -18.72401], [-53.170406, -18.726571], [-53.170604, -18.726606], [-53.170652, -18.726601], [-53.170706, -18.72656], [-53.170717, -18.726403], [-53.170341, -18.723644], [-53.169858, -18.719849], [-53.169783, -18.719524], [-53.169494, -18.719336], [-53.168855, -18.71898], [-53.168415, -18.718762], [-53.167546, -18.718244], [-53.167053, -18.717984], [-53.166323, -18.717537], [-53.164923, -18.71673], [-53.163131, -18.715642], [-53.159607, -18.713564], [-53.155165, -18.710902], [-53.155053, -18.710876]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 21, "DESC_TALHA": "C1", "AREA_TOTAL": 154.79}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.151855, -18.708808], [-53.153712, -18.709921], [-53.155053, -18.710744], [-53.15509, -18.710699], [-53.155423, -18.710008], [-53.156034, -18.708692], [-53.151855, -18.708692], [-53.151855, -18.708808]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 2, "DESC_TALHA": "A2", "AREA_TOTAL": 90.49}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.153476, -18.722953], [-53.157225, -18.723868], [-53.157333, -18.723863], [-53.157381, -18.723802], [-53.15737, -18.723634], [-53.157139, -18.722511], [-53.156973, -18.721612], [-53.156501, -18.719311], [-53.156227, -18.717863], [-53.155991, -18.716775], [-53.155766, -18.715551], [-53.155348, -18.713549], [-53.155326, -18.713361], [-53.154886, -18.711207], [-53.154881, -18.711059], [-53.154983, -18.710841], [-53.154988, -18.710795], [-53.154919, -18.710734], [-53.154307, -18.710353], [-53.151855, -18.708869], [-53.151855, -18.722582], [-53.153476, -18.722953]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 11, "DESC_TALHA": "B1", "AREA_TOTAL": 164.91}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.157499, -18.723985], [-53.1581, -18.727074], [-53.15818, -18.727409], [-53.15832, -18.728176], [-53.158416, -18.728577], [-53.158588, -18.729502], [-53.171124, -18.729502], [-53.171001, -18.728537], [-53.170953, -18.728262], [-53.170792, -18.726926], [-53.170749, -18.726723], [-53.170658, -18.726662], [-53.157874, -18.724051], [-53.157499, -18.723985]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 22, "DESC_TALHA": "C2", "AREA_TOTAL": 199.45}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.15855, -18.729502], [-53.157483, -18.724132], [-53.157434, -18.723949], [-53.157091, -18.723878], [-53.152885, -18.722842], [-53.151855, -18.722608], [-53.151855, -18.729502], [-53.15855, -18.729502]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 12, "DESC_TALHA": "B2", "AREA_TOTAL": 175.12}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.165057, -18.689764], [-53.164896, -18.690145], [-53.164521, -18.690933], [-53.161592, -18.697361], [-53.161291, -18.698036], [-53.161281, -18.698108], [-53.161367, -18.698199], [-53.168287, -18.702538], [-53.168308, -18.702528], [-53.168335, -18.702472], [-53.170701, -18.696446], [-53.17143, -18.694607], [-53.171548, -18.694322], [-53.171666, -18.694098], [-53.171672, -18.694053], [-53.171639, -18.694012], [-53.170969, -18.69358], [-53.169215, -18.692472], [-53.168957, -18.692289], [-53.168249, -18.691852], [-53.16576, -18.690252], [-53.165336, -18.689972], [-53.165057, -18.689764]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 32, "DESC_TALHA": "E2", "AREA_TOTAL": 85.27}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.171688, -18.694109], [-53.171436, -18.694673], [-53.171285, -18.695089], [-53.168448, -18.702244], [-53.168351, -18.702528], [-53.168373, -18.702589], [-53.16841, -18.702615], [-53.16937, -18.703199], [-53.17187, -18.704784], [-53.173828, -18.706004], [-53.173828, -18.695435], [-53.172728, -18.694713], [-53.172031, -18.694281], [-53.17179, -18.694104], [-53.17172, -18.694093], [-53.171688, -18.694109]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 33, "DESC_TALHA": "E3", "AREA_TOTAL": 89.58}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.161254, -18.698214], [-53.161206, -18.69826], [-53.160685, -18.699363], [-53.159822, -18.701121], [-53.159221, -18.702284], [-53.158765, -18.703128], [-53.158218, -18.7042], [-53.158051, -18.704545], [-53.158051, -18.704622], [-53.1581, -18.704667], [-53.159779, -18.705633], [-53.161544, -18.706685], [-53.163614, -18.70797], [-53.164875, -18.708692], [-53.173828, -18.708692], [-53.173828, -18.706044], [-53.161576, -18.698367], [-53.161324, -18.698219], [-53.161254, -18.698214]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 4, "DESC_TALHA": "A4", "AREA_TOTAL": 135.76}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.151855, -18.690516], [-53.151855, -18.692396], [-53.158894, -18.696659], [-53.161088, -18.698011], [-53.161232, -18.698077], [-53.161254, -18.698062], [-53.162761, -18.694729], [-53.16487, -18.690155], [-53.165009, -18.689774], [-53.164998, -18.689713], [-53.164907, -18.689622], [-53.164462, -18.689266], [-53.164237, -18.689114], [-53.163663, -18.688844], [-53.163148, -18.688626], [-53.162279, -18.688311], [-53.161265, -18.687879], [-53.153068, -18.687879], [-53.151855, -18.690516]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 31, "DESC_TALHA": "E1", "AREA_TOTAL": 116.55}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.151855, -18.700852], [-53.157633, -18.704383], [-53.157907, -18.704545], [-53.157987, -18.704556], [-53.158035, -18.704505], [-53.158658, -18.70325], [-53.159451, -18.701766], [-53.160036, -18.700618], [-53.160723, -18.6992], [-53.1612, -18.698169], [-53.161206, -18.698118], [-53.161184, -18.698082], [-53.160959, -18.697965], [-53.15951, -18.697071], [-53.151855, -18.692422], [-53.151855, -18.700852]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 3, "DESC_TALHA": "A3", "AREA_TOTAL": 98.16}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.157982, -18.704713], [-53.157944, -18.704759], [-53.157681, -18.705303], [-53.156093, -18.708692], [-53.164805, -18.708692], [-53.163008, -18.707655], [-53.16245, -18.707284], [-53.161882, -18.706934], [-53.159677, -18.705613], [-53.15811, -18.704718], [-53.158041, -18.704698], [-53.157982, -18.704713]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 1, "DESC_TALHA": "A1", "AREA_TOTAL": 121.19}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.156034, -18.708692], [-53.15752, -18.705552], [-53.157719, -18.705084], [-53.157923, -18.704708], [-53.157933, -18.704662], [-53.157917, -18.704622], [-53.157719, -18.704479], [-53.15487, -18.702767], [-53.154457, -18.702533], [-53.151855, -18.700923], [-53.151855, -18.708692], [-53.156034, -18.708692]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 2, "DESC_TALHA": "A2", "AREA_TOTAL": 90.49}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.154404, -18.685048], [-53.154361, -18.685084], [-53.154162, -18.685485], [-53.153068, -18.687879], [-53.161265, -18.687879], [-53.159757, -18.687228], [-53.159473, -18.687127], [-53.158352, -18.686649], [-53.157976, -18.686512], [-53.156823, -18.686019], [-53.15626, -18.68581], [-53.155734, -18.685561], [-53.154913, -18.685251], [-53.154489, -18.685053], [-53.154404, -18.685048]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 31, "DESC_TALHA": "E1", "AREA_TOTAL": 116.55}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.149425, -18.729502], [-53.15155, -18.739266], [-53.151571, -18.739317], [-53.151625, -18.739353], [-53.151855, -18.739358], [-53.151855, -18.729502], [-53.149425, -18.729502]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 12, "DESC_TALHA": "B2", "AREA_TOTAL": 175.12}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.151587, -18.739388], [-53.151555, -18.739429], [-53.151555, -18.739464], [-53.151855, -18.740846], [-53.151855, -18.739378], [-53.151641, -18.739373], [-53.151587, -18.739388]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 13, "DESC_TALHA": "B3", "AREA_TOTAL": 168.27}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.151855, -18.708808], [-53.151855, -18.708692], [-53.151662, -18.708692], [-53.151855, -18.708808]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 2, "DESC_TALHA": "A2", "AREA_TOTAL": 90.49}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.145107, -18.709499], [-53.145134, -18.709713], [-53.145289, -18.710465], [-53.145332, -18.710612], [-53.14773, -18.721683], [-53.147768, -18.721739], [-53.1478, -18.721749], [-53.14809, -18.72177], [-53.151855, -18.722582], [-53.151855, -18.708869], [-53.15155, -18.708692], [-53.145091, -18.708692], [-53.145107, -18.709499]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 11, "DESC_TALHA": "B1", "AREA_TOTAL": 164.91}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.147993, -18.721775], [-53.147784, -18.721785], [-53.147768, -18.7218], [-53.147768, -18.721836], [-53.148288, -18.724295], [-53.149425, -18.729502], [-53.151855, -18.729502], [-53.151855, -18.722608], [-53.148251, -18.721825], [-53.147993, -18.721775]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 12, "DESC_TALHA": "B2", "AREA_TOTAL": 175.12}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.151855, -18.690516], [-53.151222, -18.691929], [-53.151222, -18.69199], [-53.151249, -18.69204], [-53.151855, -18.692396], [-53.151855, -18.690516]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 31, "DESC_TALHA": "E1", "AREA_TOTAL": 116.55}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.151163, -18.692046], [-53.148862, -18.697046], [-53.148202, -18.698499], [-53.14817, -18.698616], [-53.148202, -18.698656], [-53.148653, -18.698905], [-53.151855, -18.700852], [-53.151855, -18.692422], [-53.151217, -18.692051], [-53.151163, -18.692046]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 3, "DESC_TALHA": "A3", "AREA_TOTAL": 98.16}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.148116, -18.698697], [-53.145354, -18.704698], [-53.145279, -18.704881], [-53.145273, -18.704932], [-53.145311, -18.704972], [-53.145874, -18.705272], [-53.147897, -18.706441], [-53.150005, -18.707716], [-53.151662, -18.708692], [-53.151855, -18.708692], [-53.151855, -18.700923], [-53.15016, -18.699871], [-53.148261, -18.698722], [-53.148192, -18.698687], [-53.148116, -18.698697]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 2, "DESC_TALHA": "A2", "AREA_TOTAL": 90.49}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-53.145241, -18.705028], [-53.145204, -18.705074], [-53.145037, -18.706075], [-53.145091, -18.708692], [-53.15155, -18.708692], [-53.147591, -18.706344], [-53.145338, -18.705033], [-53.1453, -18.705018], [-53.145241, -18.705028]]]}, "properties": {"FAZENDA": 3, "NOME_FAZ": "SAN JORGE", "TALHAO": 11, "DESC_TALHA": "B1", "AREA_TOTAL": 164.91}}]};
var talhoes = ee.FeatureCollection(talhoesGeoJson.features.map(function(f) {
  return ee.Feature(ee.Geometry(f.geometry), f.properties);
}));

var fazenda = talhoes.geometry().dissolve();
var pontosRecorte = talhoes.map(function(f) {
  return ee.Feature(f.geometry().centroid(1), {
    TALHAO: f.get('TALHAO'),
    DESC_TALHA: f.get('DESC_TALHA')
  });
});

Map.centerObject(fazenda, 13);
Map.addLayer(fazenda, {color: 'yellow'}, 'Limite fazenda');
Map.addLayer(talhoes.style({color: '#00FFFF', fillColor: '00000000', width: 1}), {}, 'Talhoes');
Map.addLayer(pontosRecorte, {color: 'red'}, 'Pontos de recorte (centroides)');

// -----------------------------
// PIPELINE ESPECIALISTA (decisao)
// -----------------------------
var CFG = {
  seasonStart: '2026-01-01',
  seasonEnd: '2026-03-31',
  recentDays: 60,
  cloudProbMax: 35,
  exportFolder: 'GEE_DECISION',
  exportScale: 10
};

function fallbackS2Image() {
  return ee.Image.constant([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    .rename(['B2', 'B3', 'B4', 'B5', 'B8', 'B8A', 'B11', 'NDVI', 'NDRE', 'GNDVI', 'NDWI', 'EVI', 'NDBI'])
    .toFloat()
    .clip(fazenda);
}

function safeCollectionMedian(coll) {
  return ee.Image(ee.Algorithms.If(
    coll.size().gt(0),
    coll.median(),
    fallbackS2Image()
  ));
}

function addS2Indices(img) {
  var ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndre = img.normalizedDifference(['B8A', 'B5']).rename('NDRE');
  var gndvi = img.normalizedDifference(['B8', 'B3']).rename('GNDVI');
  var ndwi = img.normalizedDifference(['B3', 'B8']).rename('NDWI');
  var evi = img.expression(
    '2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))',
    {nir: img.select('B8'), red: img.select('B4'), blue: img.select('B2')}
  ).rename('EVI');
  var ndbi = img.normalizedDifference(['B11', 'B8']).rename('NDBI');
  return img.addBands([ndvi, ndre, gndvi, ndwi, evi, ndbi]);
}

function getS2Collection(startDate, endDate) {
  var coll = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(fazenda)
    .filterDate(startDate, endDate)
    .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 85))
    .map(function(img) {
      // cloud mask robusto sem dependencia de join
      var qa = img.select('QA60');
      var cloudBitMask = 1 << 10;
      var cirrusBitMask = 1 << 11;
      var qaMask = qa.bitwiseAnd(cloudBitMask).eq(0).and(qa.bitwiseAnd(cirrusBitMask).eq(0));
      
    var scl = img.select('SCL');
      var mask = qaMask
      .and(scl.neq(3))   // shadow
      .and(scl.neq(8))   // cloud medium
      .and(scl.neq(9))   // cloud high
      .and(scl.neq(10))  // cirrus
      .and(scl.neq(11)); // snow

    return img.updateMask(mask)
      .divide(10000)
      .copyProperties(img, ['system:time_start']);
    })
    .map(addS2Indices);

  return coll;
}

function monthComposite(year, month) {
  var start = ee.Date.fromYMD(year, month, 1);
  var end = start.advance(1, 'month');
  var coll = getS2Collection(start, end);
  return safeCollectionMedian(coll).set({
    year: year,
    month: month,
    image_count: coll.size()
  });
}

// Periodos
var seasonStart = ee.Date(CFG.seasonStart);
var seasonEnd = ee.Date(CFG.seasonEnd).advance(1, 'day');
var endDate = ee.Date(Date.now());
var startRecent = endDate.advance(-CFG.recentDays, 'day');
var seasonYear = seasonStart.get('year');

// Sentinel-2 recente + safra
var s2Recent = getS2Collection(startRecent, endDate);
var s2Season = getS2Collection(seasonStart, seasonEnd);
var latestGood = ee.Image(ee.Algorithms.If(
  s2Recent.size().gt(0),
  s2Recent.sort('system:time_start', false).first(),
  fallbackS2Image()
));
var seasonMedian = safeCollectionMedian(s2Season);

var jan = monthComposite(seasonYear, 1);
var feb = monthComposite(seasonYear, 2);
var mar = monthComposite(seasonYear, 3);

// Terreno (GLO30 e ImageCollection -> mosaic)
var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').mosaic().clip(fazenda).rename('DEM');
var terrain = ee.Terrain.products(dem);
var slope = terrain.select('slope').rename('SLOPE');
var aspect = terrain.select('aspect').rename('ASPECT');
var hillshade = terrain.select('hillshade').rename('HILLSHADE');
var tpi = dem.subtract(dem.focal_mean({radius: 90, units: 'meters'})).rename('TPI_90m');

// Chuva (CHIRPS) e clima (ERA5 Daily)
var chirpsSeason = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
  .filterBounds(fazenda)
  .filterDate(seasonStart, seasonEnd);
var rainSeason = ee.Image(ee.Algorithms.If(
  chirpsSeason.size().gt(0),
  chirpsSeason.sum().rename('RAIN_SUM_MM'),
  ee.Image.constant(0).rename('RAIN_SUM_MM').toFloat().clip(fazenda)
));
var rainP95 = ee.Image(ee.Algorithms.If(
  chirpsSeason.size().gt(0),
  chirpsSeason.reduce(ee.Reducer.percentile([95])).rename('RAIN_P95_MM'),
  ee.Image.constant(0).rename('RAIN_P95_MM').toFloat().clip(fazenda)
));

var eraSeason = ee.ImageCollection('ECMWF/ERA5/DAILY')
  .filterBounds(fazenda)
  .filterDate(seasonStart, seasonEnd);
var tempMeanC = ee.Image(ee.Algorithms.If(
  eraSeason.size().gt(0),
  eraSeason.select('mean_2m_air_temperature').mean().subtract(273.15).rename('TEMP_MEAN_C'),
  ee.Image.constant(0).rename('TEMP_MEAN_C').toFloat().clip(fazenda)
));
var tempMaxC = ee.Image(ee.Algorithms.If(
  eraSeason.size().gt(0),
  eraSeason.select('maximum_2m_air_temperature').max().subtract(273.15).rename('TEMP_MAX_C'),
  ee.Image.constant(0).rename('TEMP_MAX_C').toFloat().clip(fazenda)
));

// Produtos de indice
var ndviLatest = latestGood.select('NDVI').rename('NDVI_LATEST');
var ndviJan = jan.select('NDVI').rename('NDVI_JAN');
var ndviFeb = feb.select('NDVI').rename('NDVI_FEB');
var ndviMar = mar.select('NDVI').rename('NDVI_MAR');
var ndviDiffJanMar = ndviMar.subtract(ndviJan).rename('NDVI_DIFF_JAN_MAR');
var ndviSeason = seasonMedian.select('NDVI').rename('NDVI_SEASON_MEDIAN');
var ndreSeason = seasonMedian.select('NDRE').rename('NDRE_SEASON_MEDIAN');
var eviSeason = seasonMedian.select('EVI').rename('EVI_SEASON_MEDIAN');
var ndwiSeason = seasonMedian.select('NDWI').rename('NDWI_SEASON_MEDIAN');

// Mapa de estresse (proxy)
var stressIndex = ee.Image.cat([
  ee.Image(1).subtract(ndviSeason).rename('LOW_VIGOR'),
  rainSeason.unitScale(0, 600).multiply(-1).add(1).rename('LOW_RAIN'),
  tempMaxC.unitScale(28, 42).rename('HEAT_PRESSURE')
]).reduce(ee.Reducer.mean()).rename('STRESS_INDEX');

// Visualizacao
Map.addLayer(latestGood.clip(fazenda), {bands: ['B4', 'B3', 'B2'], min: 0.03, max: 0.35, gamma: 1.2}, 'RGB ultimo bom');
Map.addLayer(ndviLatest.clip(fazenda), {min: 0, max: 0.9, palette: ['#8c510a', '#f6e8c3', '#5ab4ac', '#01665e']}, 'NDVI ultimo');
Map.addLayer(ndviDiffJanMar.clip(fazenda), {min: -0.4, max: 0.4, palette: ['#762a83', '#f7f7f7', '#1b7837']}, 'NDVI diff Jan-Mar');
Map.addLayer(slope.clip(fazenda), {min: 0, max: 16, palette: ['#1f77b4', '#7fc8f8', '#f4a261', '#e76f51', '#7f5539']}, 'Declividade');
Map.addLayer(stressIndex.clip(fazenda), {min: 0, max: 1, palette: ['#1a9850', '#fee08b', '#d73027']}, 'Stress Index');

// Stack para decisao por talhao
var decisionStack = ee.Image.cat([
  dem, slope, aspect, hillshade, tpi,
  rainSeason, rainP95, tempMeanC, tempMaxC,
  ndviLatest, ndviSeason, ndreSeason, eviSeason, ndwiSeason,
  ndviJan, ndviFeb, ndviMar, ndviDiffJanMar, stressIndex
]).clip(fazenda);

var reducer = ee.Reducer.mean()
  .combine({reducer2: ee.Reducer.stdDev(), sharedInputs: true})
  .combine({reducer2: ee.Reducer.percentile([10, 50, 90]), sharedInputs: true});

var talhaoDecisionStats = decisionStack.reduceRegions({
  collection: talhoes,
  reducer: reducer,
  scale: CFG.exportScale,
  tileScale: 4
});

// Serie temporal NDVI/EVI por talhao (quinzenal)
var idxSeries = s2Season
  .select(['NDVI', 'EVI', 'NDRE', 'NDWI'])
  .map(function(img) {
    var date = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd');
    var byTalhao = img.reduceRegions({
      collection: talhoes,
      reducer: ee.Reducer.mean(),
      scale: CFG.exportScale,
      tileScale: 4
    }).map(function(f) {
      return f.set('date', date);
    });
    return byTalhao;
  }).flatten();

// Serie diaria chuva/clima para fazenda
var rainDailyFarm = chirpsSeason.map(function(img) {
  var d = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd');
  var rain = img.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: fazenda,
    scale: 5500,
    maxPixels: 1e13
  }).get('precipitation');
  return ee.Feature(null, {date: d, rain_mm: rain});
});

var climateDailyFarm = eraSeason.map(function(img) {
  var d = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd');
  var vals = img.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: fazenda,
    scale: 9000,
    maxPixels: 1e13
  });
  return ee.Feature(null, {
    date: d,
    temp_mean_c: ee.Number(vals.get('mean_2m_air_temperature')).subtract(273.15),
    temp_max_c: ee.Number(vals.get('maximum_2m_air_temperature')).subtract(273.15),
    precip_m: vals.get('total_precipitation')
  });
});

// Exportacoes essenciais (substituem as antigas)
Export.image.toDrive({
  image: latestGood.select(['B4', 'B3', 'B2']).clip(fazenda),
  description: 'DECISION_latest_RGB_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_latest_RGB_SAN_JORGE',
  region: fazenda,
  scale: 10,
  maxPixels: 1e13
});

Export.image.toDrive({
  image: ee.Image.cat([ndviLatest, ndviSeason, ndreSeason, eviSeason, ndwiSeason, ndviDiffJanMar]).clip(fazenda),
  description: 'DECISION_indices_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_indices_SAN_JORGE',
  region: fazenda,
  scale: 10,
  maxPixels: 1e13
});

Export.image.toDrive({
  image: ee.Image.cat([dem, slope, tpi, rainSeason, tempMeanC, stressIndex]).clip(fazenda),
  description: 'DECISION_terrain_climate_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_terrain_climate_SAN_JORGE',
  region: fazenda,
  scale: 30,
  maxPixels: 1e13
});

Export.table.toDrive({
  collection: talhaoDecisionStats,
  description: 'DECISION_talhoes_stats_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_talhoes_stats_SAN_JORGE',
  fileFormat: 'CSV'
});

Export.table.toDrive({
  collection: idxSeries,
  description: 'DECISION_talhoes_indices_timeseries_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_talhoes_indices_timeseries_SAN_JORGE',
  fileFormat: 'CSV'
});

Export.table.toDrive({
  collection: rainDailyFarm,
  description: 'DECISION_fazenda_rain_daily_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_fazenda_rain_daily_SAN_JORGE',
  fileFormat: 'CSV'
});

Export.table.toDrive({
  collection: climateDailyFarm,
  description: 'DECISION_fazenda_climate_daily_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_fazenda_climate_daily_SAN_JORGE',
  fileFormat: 'CSV'
});

Export.table.toDrive({
  collection: pontosRecorte,
  description: 'DECISION_talhoes_centroides_SAN_JORGE',
  folder: CFG.exportFolder,
  fileNamePrefix: 'DECISION_talhoes_centroides_SAN_JORGE',
  fileFormat: 'CSV'
});

print('Talhoes:', talhoes.size());
print('S2 recentes:', s2Recent.size());
print('S2 safra:', s2Season.size());
print('Jan imgs:', jan.get('image_count'), 'Fev imgs:', feb.get('image_count'), 'Mar imgs:', mar.get('image_count'));
print('Decision stats preview:', talhaoDecisionStats.limit(5));
