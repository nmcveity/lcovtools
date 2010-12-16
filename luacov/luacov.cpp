#define LUA_LIB
#define LUACOVTOOLS_VERSION "0.2 alpha"

extern "C" 
{
#include "lua.h"
#include "lauxlib.h"
}

#include <memory.h>
#include <string.h>
#include <assert.h>

static lua_Hook s_oldHook = NULL;
static int s_oldHookMask = 0;
static int s_oldHookCount = 0;

struct luacov_File
{
	char filename[256];
	int numLines;			// size of bitfield in bits
	int* lines;				// bitfield
};

static luacov_File ** s_results = NULL;
static int s_numResults = 0;
static int s_maxResults = 0;

static const char * s_previousName = NULL;
static luacov_File * s_previousNode = NULL;

static void luacovI_resizeresults()
{
	s_maxResults += 64;
	luacov_File ** res = new luacov_File* [s_maxResults];
	memcpy(res, s_results, sizeof(luacov_File*) * s_numResults);
	delete[] s_results;
	s_results = res;
}

static luacov_File * luacovI_findfile(const char * name)
{
	assert(name);
    
    // Early out optimisation, most of the time the file requested is the same
	// as the last search.
    if (s_previousName && strcmp(s_previousName, name) == 0)
        return s_previousNode;

	// Binary search for the file
	int low = 0;
	int high = s_numResults - 1;
	int mid = 0;
	int dir = 0;
	
	while (low <= high)
	{ 
		mid = (low + high) / 2;
		dir = strcmp(s_results[mid]->filename, name);
		
		if (dir > 0)
		{ 
			high = mid - 1;
		}
		else if (dir < 0)
		{
			low = mid + 1;
		}
		else
		{
            s_previousName = s_results[mid]->filename;
            s_previousNode = s_results[mid];
            
			return s_results[mid];
		}
	}
    
	// Need to add a new one
	if (s_maxResults == s_numResults)
		luacovI_resizeresults();

	luacov_File * me = new luacov_File();

	me->lines = new int [32];
	me->numLines = 32;
    
    memset(me->lines, 0, sizeof(int) * 32); 
	strncpy(me->filename, name, sizeof(me->filename));
    
	// Insert into s_results so that s_results remains sorted on 'filename'
	int i = 0;
	
	for (; i < s_numResults; i++)
	{
		if (strcmp(s_results[i]->filename, me->filename) > 0)
			break;
	}
	
	for (int j = s_numResults; j > i; --j)
	{
		s_results[j] = s_results[j-1];
	}
	
	s_results[i] = me;
    s_previousName = s_results[i]->filename;
    s_previousNode = s_results[i];
	s_numResults++;

	return me;
}

static void luacovI_resizelinebuf(luacov_File * f, int minLines)
{
	assert(f);
	assert(minLines > 0);

	int newSize = f->numLines * 2;

	if (newSize <= minLines)
		newSize = minLines * 2;

	int * lb = new int [newSize];

	memcpy(lb, f->lines, f->numLines * sizeof(int));
	memset(lb + f->numLines, 0, (newSize - f->numLines) * sizeof(int));

	delete [] f->lines;

	f->lines = lb;
	f->numLines = newSize;
}

static inline void luacovI_setbit(int * buffer, int bitnum)
{
	buffer[bitnum >> 5] |= 1 << (bitnum & 31);
}

static void luacovI_hook(lua_State *L, lua_Debug *ar)
{
	if (s_oldHook)
		s_oldHook(L, ar);

	if (ar->event == LUA_HOOKLINE)
	{
		lua_getinfo(L, "Sl", ar);

		if (ar->source[0] == '@')
		{
			luacov_File * f = luacovI_findfile(ar->source+1);

			int requiredBufferLen = (ar->currentline >> 5) + 1;

			if (requiredBufferLen >= f->numLines)
				luacovI_resizelinebuf(f, requiredBufferLen);

			luacovI_setbit(f->lines, ar->currentline);
		}
	}
}

static void luacovI_reset()
{
	for (int i = 0; i < s_numResults; i++)
		delete s_results[i];

	delete[] s_results;

	s_numResults = 0;
	s_maxResults = 64;
	s_results = new luacov_File* [s_maxResults];
    
    s_previousName = NULL;
    s_previousNode = NULL;

	for(int i = 0; i < s_maxResults; i++)
		s_results[i] = NULL;
}

static int luacov_start(lua_State *L)
{
	if (s_results == NULL)
		luacovI_reset();

	// install hooks
	bool setHook = false;

	if (lua_gettop(L) > 0)
	{
		luaL_argcheck(L, lua_type(L,1) == LUA_TBOOLEAN, 1, "expecting boolean or nil");

		if (lua_toboolean(L, 1))
			setHook = true;
	}

	if (setHook)
	{
		s_oldHook = lua_gethook(L);
		s_oldHookMask = lua_gethookmask(L);
		s_oldHookCount = lua_gethookcount(L);

		lua_sethook(L, luacovI_hook, s_oldHookMask | LUA_MASKLINE, s_oldHookCount);
	}

	return 0;
}

static int luacov_gethookfunc(lua_State *L)
{
	lua_Hook fp = &luacovI_hook;
	void * ud = lua_newuserdata(L, sizeof(fp));
	memcpy(ud, &fp, sizeof(fp));
	return 1;
}

static int luacov_stop(lua_State *L)
{
	lua_sethook(L, s_oldHook, s_oldHookMask, s_oldHookCount);

	s_oldHook = NULL;
	s_oldHookMask = 0;
	s_oldHookCount = 0;

	return 0;
}

static int luacov_reset(lua_State *L)
{
	luacovI_reset();
	return 0;
}

static int luacovI_printf(lua_State *L)
{
	int numArgs = lua_gettop(L);

	lua_pushliteral(L, "write");
	lua_gettable(L, 1);				// find 'write' method
	lua_pushvalue(L, 1);			// push self pointer

	// format string
	lua_pushliteral(L, "string");
	lua_gettable(L, LUA_GLOBALSINDEX);
	lua_pushliteral(L, "format");
	lua_gettable(L, -2);
	lua_remove(L, -2);

	for(int i = 2; i <= numArgs; i++)
		lua_pushvalue(L, i);

	lua_call(L, numArgs-1, 1);

	const char * msg = lua_tostring(L, -1);

	// call :write(str)
	lua_call(L, 2, 0);

	return 0;
}

static int luacov_dump(lua_State *L)
{
	luaL_argcheck(L, (lua_type(L,1) == LUA_TUSERDATA) || (lua_type(L,1) == LUA_TTABLE) || (lua_type(L, 1) == LUA_TNIL), 1, 
		"expected table, userdata or nil for parameter");

	int indexOfSelf = 1;

	if (lua_gettop(L) == 0)
	{
		lua_pushliteral(L, "io");
		lua_gettable(L, LUA_GLOBALSINDEX);
		lua_pushliteral(L, "stdout");
		lua_gettable(L, -2);
		lua_remove(L, -2);

		indexOfSelf = lua_gettop(L);
	}

	lua_pushvalue(L, lua_upvalueindex(1));

	int print = lua_gettop(L);

	lua_pushvalue(L, print);
	lua_pushvalue(L, indexOfSelf);
	lua_pushliteral(L, "<lcovtools version=\"%s\">");
	lua_pushliteral(L, LUACOVTOOLS_VERSION);
	lua_call(L, 3, 0);

	for(int f = 0; f < s_numResults; f++)
	{
		luacov_File * file = s_results[f];

		lua_pushvalue(L, print);
		lua_pushvalue(L, indexOfSelf);					// self
		lua_pushliteral(L, "<file name=\"%s\">");		// format spec
		lua_pushstring(L, file->filename);				// parameters
		lua_call(L, 3, 0);

		for(int l = 0; l < file->numLines; l++)
		{
			for(int b = 0; b < 32; b++)
			{
				if ((file->lines[l] & (1 << b)) == 0)
					continue;

				lua_pushvalue(L, print);
				lua_pushvalue(L, indexOfSelf);
				lua_pushliteral(L, "\t<line number=\"%d\"/>");
				lua_pushinteger(L, l*32+b);
				lua_call(L, 3, 0);
			}
		}

		lua_pushvalue(L, print);
		lua_pushvalue(L, indexOfSelf);
		lua_pushliteral(L, "</file>");
		lua_pushstring(L, file->filename);
		lua_call(L, 3, 0);
	}

	lua_pushvalue(L, print);
	lua_pushvalue(L, indexOfSelf);
	lua_pushliteral(L, "</lcovtools>");
	lua_call(L, 2, 0);

	lua_remove(L, print);

	return 0;
}

static int luacovI_countmemusage()
{
	int bytes = s_maxResults * sizeof(luacov_File*);		// thats the size of s_results array

	for(int i = 0; i < s_numResults; i++)
	{
		bytes += sizeof(luacov_File);
		bytes += sizeof(int) * s_results[i]->numLines;
	}

	return bytes;
}

static int luacov_getstats(lua_State* L)
{
	lua_pushinteger(L, luacovI_countmemusage());
	lua_pushinteger(L, s_numResults);

	return 2;
}

static luaL_Reg contents[] = 
{
	{"start",		luacov_start},
	{"stop",		luacov_stop},
	{"reset",		luacov_reset},
	{"dump",		luacov_dump},
	{"gethookfunc",	luacov_gethookfunc},
	{"getstats",    luacov_getstats},

	{NULL, NULL},
};

extern "C" lua_Hook lcov_gethookfunc()
{
	return &luacovI_hook;
}

extern "C" int luaopen_lcovtools(lua_State *L)
{
	assert(L);

	luaL_register(L, "lcovtools", contents);

	lua_pushliteral(L, "dump");
	lua_pushcclosure(L, luacovI_printf, 0);
	lua_pushcclosure(L, luacov_dump, 1);
	lua_settable(L, -3);

	lua_pushliteral(L, "version");
	lua_pushstring(L, LUACOVTOOLS_VERSION);
	lua_settable(L, -3);

	return 1;
}

